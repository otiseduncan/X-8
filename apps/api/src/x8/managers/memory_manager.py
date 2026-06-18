import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


MEMORY_TYPES = {
    "user_profile",
    "user_preference",
    "project_fact",
    "workflow_preference",
    "assistant_behavior_rule",
    "technical_environment",
    "model_configuration",
    "tool_configuration",
    "design_preference",
    "voice_avatar_preference",
    "verified_status_pointer",
}
MEMORY_STATUSES = {"pending", "approved", "active", "superseded", "deleted", "rejected"}
MEMORY_SOURCES = {"user_explicit", "user_correction", "legacy_import_x7", "legacy_import_x6", "runtime_observation", "verified_status", "manual_admin"}
SECRET_PATTERN = re.compile(r"(api[_-]?key|password|token|secret|private[_-]?key|service_account)", re.IGNORECASE)


class ContextSeparation(BaseModel):
    memory: str = "User or project facts explicitly remembered."
    knowledge: str = "Seeded general guidance loaded from knowledge files."
    verified_status: str = "Live proof from checks that actually ran."
    preferences: str = "Approved user working preferences."


class MemoryRecord(BaseModel):
    memory_record_id: str = Field(default_factory=lambda: f"mem_{uuid4().hex[:12]}")
    memory_type: str
    status: str = "pending"
    source: str
    text: str
    confidence: float = 0.5
    source_path: str = ""
    supersedes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    embedding_id: str = ""


class MemoryProposal(BaseModel):
    memory_type: str
    source: str = "user_explicit"
    text: str
    confidence: float = 0.7
    source_path: str = ""


class MemoryApprovalDecision(BaseModel):
    memory_record_id: str
    decision: str
    supersedes: str = ""


class MemoryReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"rcpt_{uuid4().hex[:12]}")
    action_type: str
    memory_record_id: str = ""
    source: str = ""
    status: str
    confidence: float = 0.0
    embedding_used: bool = False
    vector_store_used: bool = False
    limitations: list[str] = Field(default_factory=list)


class MemorySearchResult(BaseModel):
    record: MemoryRecord
    score: float
    match_type: str


class MemoryStatus(BaseModel):
    enabled: bool
    embedding_model: str
    embedding_ready: bool
    vector_store_ready: bool
    memory_ready: bool
    pending_count: int
    active_count: int
    failure_reason: str = ""
    last_checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VectorStoreAdapter:
    def upsert_embedding(self, collection: str, item_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        raise NotImplementedError

    def search_similar(self, collection: str, vector: list[float], limit: int = 5) -> list[tuple[str, float]]:
        raise NotImplementedError

    def delete_embedding(self, collection: str, item_id: str) -> None:
        raise NotImplementedError

    def list_collections(self) -> list[str]:
        raise NotImplementedError

    def health_check(self) -> tuple[bool, str]:
        raise NotImplementedError


class LocalJsonVectorStoreAdapter(VectorStoreAdapter):
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, dict[str, dict[str, Any]]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, dict[str, dict[str, Any]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def upsert_embedding(self, collection: str, item_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        data = self._load()
        data.setdefault(collection, {})[item_id] = {"vector": vector, "metadata": metadata}
        self._save(data)

    def search_similar(self, collection: str, vector: list[float], limit: int = 5) -> list[tuple[str, float]]:
        items = self._load().get(collection, {})
        scored = [(item_id, _cosine(vector, payload.get("vector", []))) for item_id, payload in items.items()]
        return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]

    def delete_embedding(self, collection: str, item_id: str) -> None:
        data = self._load()
        data.get(collection, {}).pop(item_id, None)
        self._save(data)

    def list_collections(self) -> list[str]:
        return sorted(self._load().keys())

    def health_check(self) -> tuple[bool, str]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            return True, ""
        except OSError as exc:
            return False, str(exc)


class OllamaEmbeddingAdapter:
    def __init__(self, ollama_adapter: Any, model: str) -> None:
        self.ollama_adapter = ollama_adapter
        self.model = model

    def embed(self, text: str) -> tuple[bool, list[float], str]:
        return self.ollama_adapter.embed(self.model, text)


class EmbeddingManager:
    def __init__(self, adapter: OllamaEmbeddingAdapter, vector_store: VectorStoreAdapter) -> None:
        self.adapter = adapter
        self.vector_store = vector_store

    def readiness(self) -> tuple[bool, int, str]:
        vector_ready, vector_reason = self.vector_store.health_check()
        ok, embedding, reason = self.adapter.embed("XV8 embedding readiness")
        if not vector_ready:
            return False, 0, vector_reason
        if not ok or not embedding:
            return False, 0, reason or "Embedding model did not return a vector."
        return True, len(embedding), ""


class MemoryPolicyManager:
    def validate_proposal(self, proposal: MemoryProposal) -> list[str]:
        errors: list[str] = []
        if proposal.memory_type not in MEMORY_TYPES:
            errors.append(f"Unsupported memory type: {proposal.memory_type}")
        if proposal.source not in MEMORY_SOURCES:
            errors.append(f"Unsupported memory source: {proposal.source}")
        if SECRET_PATTERN.search(proposal.text):
            errors.append("Secret-like content is blocked from memory.")
        return errors


class MemoryWriteManager:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def load(self) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [MemoryRecord.model_validate(item) for item in payload]

    def save(self, records: list[MemoryRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([item.model_dump(mode="json") for item in records], indent=2), encoding="utf-8")

    def upsert(self, record: MemoryRecord) -> MemoryRecord:
        records = [item for item in self.load() if item.memory_record_id != record.memory_record_id]
        record.updated_at = datetime.now(timezone.utc)
        records.append(record)
        self.save(records)
        return record


class MemoryApprovalManager:
    def __init__(self, writer: MemoryWriteManager) -> None:
        self.writer = writer

    def decide(self, decision: MemoryApprovalDecision) -> tuple[MemoryRecord | None, MemoryReceipt]:
        records = self.writer.load()
        target = next((item for item in records if item.memory_record_id == decision.memory_record_id), None)
        if not target:
            return None, MemoryReceipt(action_type="memory_approval_failed", status="not_found", memory_record_id=decision.memory_record_id)
        if decision.decision == "approve":
            target.status = "active"
            if decision.supersedes:
                target.supersedes = decision.supersedes
                for item in records:
                    if item.memory_record_id == decision.supersedes:
                        item.status = "superseded"
        elif decision.decision == "reject":
            target.status = "rejected"
        elif decision.decision == "delete":
            target.status = "deleted"
        else:
            return target, MemoryReceipt(action_type="memory_approval_failed", status="unsupported_decision", memory_record_id=target.memory_record_id)
        self.writer.save(records)
        return target, MemoryReceipt(action_type=f"memory_{target.status}", status=target.status, memory_record_id=target.memory_record_id, source=target.source, confidence=target.confidence)


class MemorySearchManager:
    def keyword_search(self, records: list[MemoryRecord], query: str, limit: int) -> list[MemorySearchResult]:
        terms = {term for term in re.findall(r"[a-z0-9_:-]+", query.lower()) if len(term) > 2}
        results: list[MemorySearchResult] = []
        for record in records:
            if record.status != "active":
                continue
            haystack = record.text.lower()
            hits = sum(1 for term in terms if term in haystack)
            if hits:
                score = min(1.0, hits / max(1, len(terms))) * record.confidence
                results.append(MemorySearchResult(record=record, score=score, match_type="keyword"))
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]


class MemoryRecallManager:
    def __init__(self, writer: MemoryWriteManager, searcher: MemorySearchManager) -> None:
        self.writer = writer
        self.searcher = searcher

    def recall(self, query: str, limit: int = 5) -> tuple[list[MemorySearchResult], MemoryReceipt]:
        results = self.searcher.keyword_search(self.writer.load(), query, limit)
        receipt = MemoryReceipt(action_type="memory_recalled", status="ready" if results else "no_matches", embedding_used=False, vector_store_used=False, limitations=["Semantic recall unavailable; keyword fallback used."])
        return results, receipt


class BrainRecallManager:
    def __init__(self, recall_manager: MemoryRecallManager) -> None:
        self.recall_manager = recall_manager

    def context_items(self, query: str, limit: int = 5) -> tuple[list[str], MemoryReceipt]:
        results, receipt = self.recall_manager.recall(query, limit)
        return [f"{item.record.memory_type} [{item.record.source}, confidence={item.record.confidence:.2f}]: {item.record.text}" for item in results], receipt


class MemoryManager:
    name = "memory"
    version = "0.2.0"

    def __init__(self, storage_path: str = "/app/runtime/memory/memory-records.json") -> None:
        self.policy = MemoryPolicyManager()
        self.writer = MemoryWriteManager(storage_path)
        self.approvals = MemoryApprovalManager(self.writer)
        self.recall_manager = MemoryRecallManager(self.writer, MemorySearchManager())
        self.brain_recall = BrainRecallManager(self.recall_manager)

    def separation(self) -> ContextSeparation:
        return ContextSeparation()

    def status(self, enabled: bool, embedding_model: str, embedding_ready: bool, vector_store_ready: bool, failure_reason: str = "") -> MemoryStatus:
        records = self.writer.load()
        memory_ready = enabled and embedding_ready and vector_store_ready
        return MemoryStatus(
            enabled=enabled,
            embedding_model=embedding_model,
            embedding_ready=embedding_ready,
            vector_store_ready=vector_store_ready,
            memory_ready=memory_ready,
            pending_count=sum(1 for item in records if item.status == "pending"),
            active_count=sum(1 for item in records if item.status == "active"),
            failure_reason="" if memory_ready else failure_reason,
        )

    def propose(self, proposal: MemoryProposal) -> tuple[MemoryRecord | None, MemoryReceipt]:
        errors = self.policy.validate_proposal(proposal)
        if errors:
            return None, MemoryReceipt(action_type="memory_proposal_created", status="blocked", source=proposal.source, confidence=proposal.confidence, limitations=errors)
        status = "approved" if proposal.source == "user_explicit" and proposal.confidence >= 0.95 else "pending"
        record = MemoryRecord(memory_type=proposal.memory_type, status=status, source=proposal.source, text=proposal.text, confidence=proposal.confidence, source_path=proposal.source_path)
        if status == "approved":
            record.status = "active"
        self.writer.upsert(record)
        return record, MemoryReceipt(action_type="memory_proposal_created", status=record.status, memory_record_id=record.memory_record_id, source=record.source, confidence=record.confidence)

    def approve(self, decision: MemoryApprovalDecision) -> tuple[MemoryRecord | None, MemoryReceipt]:
        return self.approvals.decide(decision)

    def recall(self, query: str, limit: int = 5) -> tuple[list[MemorySearchResult], MemoryReceipt]:
        return self.recall_manager.recall(query, limit)


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_mag = math.sqrt(sum(a * a for a in left))
    right_mag = math.sqrt(sum(b * b for b in right))
    if not left_mag or not right_mag:
        return 0.0
    return dot / (left_mag * right_mag)
