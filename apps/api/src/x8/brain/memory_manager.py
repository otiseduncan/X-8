import re
from dataclasses import dataclass, field
from typing import Any

from x8.brain.brain_receipts import brain_card, brain_receipt
from x8.brain.active_focus_manager import ActiveFocusManager
from x8.brain.embedding_client import OllamaEmbeddingClient
from x8.brain.memory_candidate_extractor import MemoryCandidateExtractor
from x8.brain.memory_policy import MemoryPolicyManager
from x8.brain.memory_store import BrainMemoryStore
from x8.contracts.receipts import Receipt

MISS_PHRASE = "I don’t have a saved memory for that yet."


@dataclass
class BrainCommandResult:
    handled: bool
    message: str
    status: str = "passed"
    receipts: list[Receipt] = field(default_factory=list)
    cards: list[Any] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


class BrainMemoryManager:
    def __init__(
        self,
        database_url: str,
        memory_enabled: bool = True,
        global_enabled: bool = True,
        project_enabled: bool = True,
        session_enabled: bool = True,
        auto_capture_enabled: bool = True,
        auto_capture_min_confidence: float = 0.7,
        auto_capture_max_per_turn: int = 3,
        auto_capture_receipts_enabled: bool = True,
        semantic_retrieval_enabled: bool = True,
        embedding_enabled: bool = True,
        embedding_client: OllamaEmbeddingClient | None = None,
        embedding_model: str = "nomic-embed-text:latest",
        retrieval_max_results: int = 5,
        retrieval_min_score: float = 0.2,
    ) -> None:
        self.store = BrainMemoryStore(database_url)
        self.policy = MemoryPolicyManager()
        self.extractor = MemoryCandidateExtractor()
        self.focus = ActiveFocusManager(self.store)
        self.memory_enabled = memory_enabled
        self.global_enabled = global_enabled
        self.project_enabled = project_enabled
        self.session_enabled = session_enabled
        self.auto_capture_default_enabled = auto_capture_enabled
        self.auto_capture_min_confidence = auto_capture_min_confidence
        self.auto_capture_max_per_turn = auto_capture_max_per_turn
        self.auto_capture_receipts_enabled = auto_capture_receipts_enabled
        self.semantic_retrieval_enabled = semantic_retrieval_enabled
        self.embedding_enabled = embedding_enabled
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model
        self.retrieval_max_results = retrieval_max_results
        self.retrieval_min_score = retrieval_min_score

    def status(self) -> dict[str, Any]:
        data = self.store.status()
        auto_capture_enabled = self.auto_capture_enabled()
        data["enabled"] = self.memory_enabled
        data["global_memory_enabled"] = self.global_enabled
        data["project_memory_enabled"] = self.project_enabled
        data["session_memory_enabled"] = self.session_enabled
        data["session_memory_mode"] = "enabled" if self.session_enabled else "disabled"
        data["reads_allowed"] = self.memory_enabled
        data["writes_allowed"] = self.memory_enabled and self.global_enabled
        data["storage_backend"] = "postgres"
        data["auto_capture_enabled"] = auto_capture_enabled
        data["auto_capture_min_confidence"] = self.auto_capture_min_confidence
        data["auto_capture_max_per_turn"] = self.auto_capture_max_per_turn
        data["auto_capture_receipts_enabled"] = self.auto_capture_receipts_enabled
        data["semantic_retrieval_enabled"] = self.semantic_retrieval_enabled
        data["embedding_enabled"] = self.embedding_enabled
        data["embedding_model"] = self.embedding_model
        data["embedding_available"] = self.embedding_status()["available"]
        data["retrieval_min_score"] = self.retrieval_min_score
        data["retrieval_max_results"] = self.retrieval_max_results
        return data

    def embedding_status(self) -> dict[str, Any]:
        indexed = self.store.semantic_index_count()
        if not self.embedding_enabled:
            return {"enabled": False, "available": False, "embedding_model": self.embedding_model, "indexed_memory_count": indexed, "failure_reason": "Embedding is disabled."}
        if not self.embedding_client:
            return {"enabled": True, "available": False, "embedding_model": self.embedding_model, "indexed_memory_count": indexed, "failure_reason": "Embedding client unavailable."}
        result = self.embedding_client.embed("XV8 embedding readiness")
        failure_reason = "" if result.ok else f"Embedding unavailable: {result.failure_reason or 'unknown'}"
        return {"enabled": True, "available": result.ok, "embedding_model": result.model, "indexed_memory_count": indexed, "failure_reason": failure_reason}

    def auto_capture_enabled(self) -> bool:
        value = self.store.runtime_setting("auto_capture_enabled", "true" if self.auto_capture_default_enabled else "false")
        return value.lower() == "true"

    def set_auto_capture_enabled(self, enabled: bool) -> dict[str, Any]:
        self.store.set_runtime_setting("auto_capture_enabled", "true" if enabled else "false")
        return self.status()

    def handle_chat_command(self, message: str, session_id: str = "", project_scope: str = "") -> BrainCommandResult:
        lowered = message.strip().lower()
        if lowered.startswith("remember that ") or lowered.startswith("remember this "):
            content = re.sub(r"(?i)^remember (that|this)\s+", "", message.strip()).strip()
            return self.remember(content, session_id=session_id, project_scope=project_scope)
        if lowered.startswith("forget that ") or lowered.startswith("forget this "):
            content = re.sub(r"(?i)^forget (that|this)\s+", "", message.strip()).strip()
            return self.forget(content, project_scope=project_scope, session_scope=session_id)
        if lowered.startswith("what do you remember"):
            query = re.sub(r"(?i)^what do you remember( about)?\s*", "", message.strip()).strip(" ?")
            return self.retrieve(query or message, project_scope=project_scope, session_scope=session_id)
        if lowered.startswith("update your focus to "):
            focus = re.sub(r"(?i)^update your focus to\s+", "", message.strip()).strip()
            return self.set_focus(focus, session_id=session_id, project_scope=project_scope)
        if lowered in {"what are we currently working on?", "what are we currently working on", "what are we working on?", "what are we working on"}:
            answer = self.focus.current_work_answer(session_id=session_id, project_scope=project_scope)
            receipt = brain_receipt("brain.focus_retrieved", "passed", "Active focus retrieved.", {"session_id": session_id})
            return BrainCommandResult(True, answer, receipts=[receipt], cards=[brain_card("Active focus", "passed", answer)])
        return BrainCommandResult(False, "")

    def remember(self, content: str, session_id: str = "", project_scope: str = "", session_scope: str = "", global_scope: bool = True) -> BrainCommandResult:
        disabled = self._write_disabled(project_scope=project_scope, session_scope=session_scope, global_scope=global_scope)
        if disabled:
            receipt = brain_receipt("brain.memory_blocked", "disabled", disabled)
            return BrainCommandResult(True, disabled, "disabled", [receipt])
        decision = self.policy.decide(content)
        if decision.blocked:
            receipt = brain_receipt("brain.memory_blocked", "blocked", "Memory blocked because it looked like a secret.", {"policy": "secret_blocked"})
            return BrainCommandResult(True, "I can’t save secrets or credentials in memory.", "blocked", [receipt], [brain_card("Memory blocked", "blocked", "Secret-like content was not saved.")])
        if decision.requires_approval:
            summary = self._summary(decision.redacted_content or content)
            record = self.store.create_memory(
                summary,
                layer="pending",
                memory_type="approval_required",
                title=self._title(summary),
                summary=summary,
                source_turn_id=session_id,
                sensitivity=decision.sensitivity,
                active=False,
                requires_approval=True,
                approved_by_user=False,
                tags=["pending", "approval_required"],
                project_scope=project_scope,
                session_scope=session_scope,
                global_scope=global_scope,
            )
            receipt = brain_receipt("brain.memory_approval_required", "approval_required", "Sensitive memory requires approval before save.", {"sensitivity": decision.sensitivity, "memory_id": record.get("id")})
            return BrainCommandResult(True, "That memory needs approval before I save it.", "approval_required", [receipt], [brain_card("Memory needs approval", "approval_required", "That memory needs approval before I save it.", {"memory_id": record.get("id")})], {"memory": record})
        summary = self._summary(content)
        record = self.store.create_memory(
            summary,
            layer=self._layer(summary),
            memory_type=self._type(summary),
            title=self._title(summary),
            summary=summary,
            source_turn_id=session_id,
            sensitivity=decision.sensitivity,
            requires_approval=False,
            approved_by_user=True,
            tags=self._tags(summary),
            project_scope=project_scope,
            session_scope=session_scope,
            global_scope=global_scope,
        )
        self._index_memory(record)
        message = f"Remembered: {summary}."
        receipt = brain_receipt("brain.memory_remembered", "passed", message, {"memory_id": record.get("id"), "layer": record.get("layer"), "type": record.get("type")})
        return BrainCommandResult(True, message, "passed", [receipt], [brain_card("Memory saved", "passed", message, {"memory_id": record.get("id")})], {"memory": record})

    def retrieve(self, query: str, limit: int = 3, project_scope: str = "", session_scope: str = "") -> BrainCommandResult:
        if not self.memory_enabled:
            receipt = brain_receipt("brain.memory_retrieved", "disabled", "Brain memory is disabled.", {"query": query})
            return BrainCommandResult(True, "Brain memory is disabled.", "disabled", [receipt], [brain_card("Memory recall", "disabled", "Brain memory is disabled.")])
        matches, proof = self._retrieve_with_proof(query, limit=limit, project_scope=project_scope, session_scope=session_scope)
        if not matches:
            receipt = brain_receipt("brain.memory_retrieved", "no_matches", MISS_PHRASE, {"query": query, "count": 0, **proof})
            return BrainCommandResult(True, MISS_PHRASE, "passed", [receipt], [brain_card("Memory recall", "no_matches", MISS_PHRASE)])
        summaries = [str(item.get("summary") or item.get("content")) for item in matches]
        if len(summaries) == 1:
            answer = f"You prefer {self._preference_fragment(summaries[0])}." if "prefer" in summaries[0].lower() else summaries[0]
        else:
            answer = "Here is what I remember: " + "; ".join(summaries) + "."
        receipt = brain_receipt("brain.memory_retrieved", "passed", "Memory retrieved.", {"count": len(matches), "memory_ids": [item["id"] for item in matches], **proof})
        return BrainCommandResult(True, answer, "passed", [receipt], [brain_card("Memory recall", "passed", "Retrieved saved memory.", {"count": len(matches), "retrieval_mode": proof.get("retrieval_mode")})], {"memories": matches, "retrieval_proof": proof})

    def auto_capture(
        self,
        source_text: str,
        *,
        lane: str,
        session_id: str = "",
        project_scope: str = "",
        session_scope: str = "",
    ) -> BrainCommandResult:
        if not self._auto_capture_lane_allowed(lane):
            return BrainCommandResult(False, "")
        if not self.auto_capture_enabled():
            return BrainCommandResult(False, "", data={"skipped": "disabled"})
        if not self.memory_enabled or not self.global_enabled:
            return BrainCommandResult(False, "", data={"skipped": "memory_disabled"})
        candidates = self.extractor.extract(source_text, source_turn_id=session_id, project_scope=project_scope, session_scope=session_scope or session_id)
        visible_receipts: list[Receipt] = []
        visible_cards: list[Any] = []
        saved: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        processed: list[dict[str, Any]] = []
        for candidate in candidates[: max(1, self.auto_capture_max_per_turn)]:
            candidate_data = candidate.as_dict()
            decision = self.policy.decide_candidate(candidate, min_confidence=self.auto_capture_min_confidence)
            candidate_data["sensitivity"] = decision.sensitivity if decision.sensitivity != "low" else candidate_data.get("sensitivity", "low")
            candidate_data["decision"] = decision.decision
            if decision.decision == "blocked":
                recorded = self.store.record_candidate(candidate_data, decision="blocked", reason=decision.reason)
                processed.append(recorded)
                receipt = brain_receipt("brain.memory_candidate_blocked", "blocked", "Memory blocked: secret-like content was not saved.", {"candidate_id": recorded.get("id")})
                visible_receipts.append(receipt)
                visible_cards.append(brain_card("Memory blocked", "blocked", "Memory blocked: secret-like content was not saved."))
                continue
            if decision.decision == "ignored":
                recorded = self.store.record_candidate(candidate_data, decision="ignored", reason=decision.reason)
                self.store.record_event("", "candidate_ignored", decision.reason, "brain")
                processed.append(recorded)
                continue
            duplicate_session_scope = (session_scope or session_id) if candidate.scope == "session" else ""
            duplicate = self.store.find_duplicate_memory(candidate.summary, layer=candidate.layer, memory_type=candidate.type, project_scope=project_scope, session_scope=duplicate_session_scope)
            if not duplicate and candidate.type == "correction":
                duplicate = self.store.find_correction_target(candidate.summary, project_scope=project_scope, session_scope=duplicate_session_scope)
            if duplicate and decision.decision == "auto_save":
                if candidate.type == "correction":
                    updated = self.store.update_memory(duplicate["id"], {"title": candidate.suggested_title, "content": candidate.suggested_content, "summary": candidate.summary, "tags": json_tags(["auto", "correction"])})
                    self.store.record_event(duplicate["id"], "correction_applied", f"Updated memory: {candidate.summary}", "brain")
                    recorded = self.store.record_candidate(candidate_data, decision="correction", reason="Clear correction updated an existing memory.", linked_memory_id=duplicate["id"])
                    processed.append(recorded)
                    if updated:
                        saved.append(updated)
                    visible_receipts.append(brain_receipt("brain.memory_correction_applied", "updated", "Updated memory: answer style preference.", {"memory_id": duplicate["id"], "candidate_id": recorded.get("id")}))
                    visible_cards.append(brain_card("Memory updated", "updated", "Updated memory: answer style preference.", {"memory_id": duplicate["id"]}))
                    continue
                self.store.touch_memory(duplicate["id"], "duplicate_detected", f"Already remembered: {duplicate.get('summary') or duplicate.get('content')}")
                recorded = self.store.record_candidate(candidate_data, decision="duplicate", reason="Duplicate candidate matched an existing memory.", linked_memory_id=duplicate["id"])
                processed.append(recorded)
                visible_receipts.append(brain_receipt("brain.memory_duplicate", "duplicate", f"Already remembered: {duplicate.get('summary') or duplicate.get('content')}.", {"memory_id": duplicate["id"], "candidate_id": recorded.get("id")}))
                visible_cards.append(brain_card("Already remembered", "duplicate", f"Already remembered: {duplicate.get('summary') or duplicate.get('content')}.", {"memory_id": duplicate["id"]}))
                continue
            if decision.decision == "pending_approval":
                memory = self.store.create_memory(
                    decision.redacted_content or candidate.suggested_content,
                    layer="pending",
                    memory_type="approval_required",
                    title=candidate.suggested_title,
                    summary=decision.redacted_content or candidate.summary,
                    source="auto_capture",
                    source_turn_id=session_id,
                    source_tool=candidate.source_tool,
                    provenance="auto_capture_candidate",
                    confidence=candidate.confidence,
                    sensitivity=decision.sensitivity,
                    active=False,
                    requires_approval=True,
                    approved_by_user=False,
                    tags=["pending", "auto_capture"],
                    project_scope=project_scope,
                    session_scope=session_scope or session_id,
                    global_scope=candidate.global_scope,
                )
                recorded = self.store.record_candidate(candidate_data, decision="pending_approval", reason=decision.reason, linked_memory_id=memory.get("id", ""))
                self.store.record_event(memory["id"], "candidate_pending_approval", "Memory pending approval.", "brain")
                pending.append(memory)
                processed.append(recorded)
                visible_receipts.append(brain_receipt("brain.memory_candidate_pending", "pending_approval", "Memory pending approval: sensitive or uncertain memory.", {"memory_id": memory.get("id"), "candidate_id": recorded.get("id")}))
                visible_cards.append(brain_card("Memory pending approval", "pending_approval", "Memory pending approval: sensitive or uncertain memory.", {"memory_id": memory.get("id")}))
                continue
            if decision.decision == "auto_save":
                memory = self.store.create_memory(
                    candidate.suggested_content,
                    layer=candidate.layer,
                    memory_type=candidate.type,
                    title=candidate.suggested_title,
                    summary=candidate.summary,
                    source="auto_capture",
                    source_turn_id=session_id,
                    source_tool=candidate.source_tool,
                    provenance="auto_capture_candidate",
                    confidence=candidate.confidence,
                    sensitivity=decision.sensitivity,
                    requires_approval=False,
                    approved_by_user=True,
                    tags=["auto", candidate.type],
                    project_scope=project_scope,
                    session_scope=session_scope or session_id if candidate.scope == "session" else "",
                    global_scope=candidate.scope != "session",
                )
                self._index_memory(memory)
                event_type = "auto_saved"
                if candidate.type == "active_work_context":
                    self.set_focus(candidate.summary, session_id=session_id, project_scope=project_scope)
                self.store.record_event(memory["id"], event_type, f"Auto-saved memory: {candidate.summary}", "brain")
                recorded = self.store.record_candidate(candidate_data, decision="auto_save", reason=decision.reason, linked_memory_id=memory.get("id", ""))
                saved.append(memory)
                processed.append(recorded)
                visible_receipts.append(brain_receipt("brain.memory_auto_saved", "auto_saved", f"Remembered: {candidate.summary}.", {"memory_id": memory.get("id"), "candidate_id": recorded.get("id")}))
                visible_cards.append(brain_card("Memory saved", "auto_saved", f"Remembered: {candidate.summary}.", {"memory_id": memory.get("id")}))
        if not visible_receipts and not processed:
            return BrainCommandResult(False, "")
        if self.auto_capture_receipts_enabled:
            visible_receipts = visible_receipts[: self.auto_capture_max_per_turn]
            visible_cards = visible_cards[: self.auto_capture_max_per_turn]
        else:
            visible_receipts = []
            visible_cards = []
        return BrainCommandResult(True, "", "passed", visible_receipts, visible_cards, {"candidates": processed, "saved": saved, "pending": pending})

    def forget(self, query: str, project_scope: str = "", session_scope: str = "") -> BrainCommandResult:
        target = self.store.search(query, limit=1, project_scope=project_scope, session_scope=session_scope)
        target = target[0] if target else None
        if not target:
            receipt = brain_receipt("brain.memory_forget", "no_matches", MISS_PHRASE, {"query": query})
            return BrainCommandResult(True, MISS_PHRASE, "passed", [receipt], [brain_card("Memory forget", "no_matches", MISS_PHRASE)])
        forgotten = self.store.soft_delete_memory(target["id"])
        summary = str((forgotten or target).get("summary") or (forgotten or target).get("content"))
        message = f"Forgotten: {summary}."
        receipt = brain_receipt("brain.memory_forgotten", "passed", message, {"memory_id": target["id"]})
        return BrainCommandResult(True, message, "passed", [receipt], [brain_card("Memory forgotten", "passed", message)], {"memory": forgotten or target})

    def set_focus(self, focus: str, session_id: str = "", project_scope: str = "") -> BrainCommandResult:
        data = self.focus.set_focus(focus, session_id=session_id, project_scope=project_scope)
        message = f"Focus updated: {focus}."
        receipt = brain_receipt("brain.focus_updated", "passed", message, {"focus_id": data["id"], "session_id": session_id})
        return BrainCommandResult(True, message, "passed", [receipt], [brain_card("Focus updated", "passed", message)], {"focus": data})

    def update_memory(self, memory_id: str, patch: dict[str, Any]) -> BrainCommandResult:
        content = str(patch.get("content") or "")
        if content:
            decision = self.policy.decide(content)
            if decision.blocked:
                receipt = brain_receipt("brain.memory_update_blocked", "blocked", "Memory update blocked because it looked like a secret.", {"memory_id": memory_id})
                return BrainCommandResult(True, "I can’t save secrets or credentials in memory.", "blocked", [receipt])
            if decision.requires_approval:
                patch["requires_approval"] = True
                patch["approved_by_user"] = False
                patch["active"] = False
        memory = self.store.update_memory(memory_id, patch)
        if not memory:
            receipt = brain_receipt("brain.memory_update", "missing", "Brain memory not found.", {"memory_id": memory_id})
            return BrainCommandResult(True, "Brain memory not found.", "missing", [receipt])
        receipt = brain_receipt("brain.memory_updated", "updated", "Brain memory updated.", {"memory_id": memory_id})
        self._index_memory(memory)
        return BrainCommandResult(True, "Brain memory updated.", "updated", [receipt], [brain_card("Memory updated", "updated", "Brain memory updated.")], {"memory": memory})

    def approve(self, memory_id: str) -> BrainCommandResult:
        memory = self.store.approve_memory(memory_id)
        if not memory:
            receipt = brain_receipt("brain.memory_approve", "missing", "Brain memory not found.", {"memory_id": memory_id})
            return BrainCommandResult(True, "Brain memory not found.", "missing", [receipt])
        receipt = brain_receipt("brain.memory_approved", "approved", "Brain memory approved.", {"memory_id": memory_id})
        self._index_memory(memory)
        return BrainCommandResult(True, "Brain memory approved.", "approved", [receipt], [brain_card("Memory approved", "approved", "Brain memory approved.")], {"memory": memory})

    def reject(self, memory_id: str) -> BrainCommandResult:
        memory = self.store.reject_memory(memory_id)
        if not memory:
            receipt = brain_receipt("brain.memory_reject", "missing", "Brain memory not found.", {"memory_id": memory_id})
            return BrainCommandResult(True, "Brain memory not found.", "missing", [receipt])
        receipt = brain_receipt("brain.memory_rejected", "rejected", "Brain memory rejected.", {"memory_id": memory_id})
        return BrainCommandResult(True, "Brain memory rejected.", "rejected", [receipt], [brain_card("Memory rejected", "rejected", "Brain memory rejected.")], {"memory": memory})

    def reactivate(self, memory_id: str) -> BrainCommandResult:
        memory = self.store.reactivate_memory(memory_id)
        if not memory:
            receipt = brain_receipt("brain.memory_reactivate", "missing", "Brain memory not found.", {"memory_id": memory_id})
            return BrainCommandResult(True, "Brain memory not found.", "missing", [receipt])
        receipt = brain_receipt("brain.memory_reactivated", "reactivated", "Brain memory reactivated.", {"memory_id": memory_id})
        self._index_memory(memory)
        return BrainCommandResult(True, "Brain memory reactivated.", "reactivated", [receipt], [brain_card("Memory reactivated", "reactivated", "Brain memory reactivated.")], {"memory": memory})

    def reindex(self) -> BrainCommandResult:
        indexed = 0
        skipped = 0
        for memory in self.store.indexable_memories():
            if self._index_memory(memory):
                indexed += 1
            else:
                skipped += 1
        message = f"Reindexed {indexed} active Brain memories."
        receipt = brain_receipt("brain.memory_reindexed", "passed", message, {"indexed": indexed, "skipped": skipped, "embedding_model": self.embedding_model})
        return BrainCommandResult(True, message, "passed", [receipt], [brain_card("Memory reindexed", "passed", message)], {"indexed": indexed, "skipped": skipped, "embedding_status": self.embedding_status()})

    def _retrieve_with_proof(self, query: str, limit: int = 3, project_scope: str = "", session_scope: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
        effective_limit = min(limit or self.retrieval_max_results, self.retrieval_max_results)
        if query.startswith("brain_mem_"):
            memory = self.store.get_memory(query)
            selected = [memory] if memory and self.store.is_indexable_memory(memory) else []
            proof = self.store.retrieval_proof(retrieval_mode="exact" if selected else "none", selected=selected, embedding_available=bool(self.embedding_client), embedding_model=self.embedding_model)
            self.store.record_retrieval(query, selected, proof)
            return selected, proof
        if self.semantic_retrieval_enabled and self.embedding_enabled and self.embedding_client:
            embedded = self.embedding_client.embed(query)
            if embedded.ok:
                selected, scores, candidate_count = self.store.semantic_search(embedded.vector, limit=effective_limit, min_score=self.retrieval_min_score, project_scope=project_scope, session_scope=session_scope)
                if selected:
                    proof = self.store.retrieval_proof(retrieval_mode="semantic", selected=selected, scores=scores, embedding_available=True, embedding_model=embedded.model, candidate_count=candidate_count)
                    self.store.record_retrieval(query, selected, proof)
                    return selected, proof
                fallback_reason = "Semantic retrieval found no memory above threshold."
            else:
                fallback_reason = embedded.failure_reason or "Embedding unavailable."
            selected, keyword_proof = self.store.keyword_search_with_proof(query, limit=effective_limit, project_scope=project_scope, session_scope=session_scope, record=False)
            keyword_proof.update({"retrieval_mode": "keyword" if selected else "none", "fallback_used": True, "fallback_reason": fallback_reason, "embedding_available": False, "embedding_model": self.embedding_model})
            self.store.record_retrieval(query, selected, keyword_proof)
            return selected, keyword_proof
        selected, proof = self.store.keyword_search_with_proof(query, limit=effective_limit, project_scope=project_scope, session_scope=session_scope, record=False)
        proof.update({"fallback_used": self.semantic_retrieval_enabled, "fallback_reason": "Semantic retrieval disabled or embedding unavailable.", "embedding_model": self.embedding_model})
        self.store.record_retrieval(query, selected, proof)
        return selected, proof

    def _index_memory(self, memory: dict[str, Any] | None) -> bool:
        if not memory or not self.embedding_enabled or not self.embedding_client or not self.store.is_indexable_memory(memory):
            return False
        current = self.store.embedding_for(memory["id"])
        content_hash = self.store.embedding_content_hash(memory)
        if current and current.get("active") and current.get("content_hash") == content_hash and current.get("embedding_model") == self.embedding_model:
            return True
        result = self.embedding_client.embed(self.store.embedding_text(memory))
        if not result.ok:
            self.store.record_event(memory["id"], "embedding_unavailable", f"Embedding unavailable: {result.failure_reason}", "brain")
            return False
        self.store.upsert_embedding(memory, result.vector, result.model)
        return True

    def _summary(self, content: str) -> str:
        cleaned = content.strip().rstrip(".")
        if re.match(r"(?i)^i prefer ", cleaned):
            return "you prefer " + cleaned[9:]
        if re.match(r"(?i)^my preference is ", cleaned):
            return "you prefer " + cleaned[17:]
        return cleaned

    def _title(self, summary: str) -> str:
        return summary[:80]

    def _layer(self, summary: str) -> str:
        return "preferences" if "prefer" in summary.lower() or "answer" in summary.lower() else "memory"

    def _type(self, summary: str) -> str:
        return "communication_preference" if "answer" in summary.lower() or "senior-engineer" in summary.lower() else "manual_memory"

    def _tags(self, summary: str) -> list[str]:
        tags = ["manual"]
        lower = summary.lower()
        if "answer" in lower:
            tags.append("answers")
        if "prefer" in lower:
            tags.append("preference")
        return tags

    def _preference_fragment(self, summary: str) -> str:
        return re.sub(r"(?i)^you prefer\s+", "", summary).rstrip(".")

    def _write_disabled(self, project_scope: str, session_scope: str, global_scope: bool) -> str:
        if not self.memory_enabled:
            return "Brain memory is disabled."
        if global_scope and not self.global_enabled:
            return "Global Brain memory writes are disabled."
        if project_scope and not self.project_enabled:
            return "Project Brain memory writes are disabled."
        if session_scope and not self.session_enabled:
            return "Session Brain memory writes are disabled."
        return ""

    def _auto_capture_lane_allowed(self, lane: str) -> bool:
        if lane.startswith("brain_"):
            return False
        if lane.startswith("github_") or lane == "self_build":
            return False
        if lane in {"approval_required_action", "attachment_question", "repo_inspection"}:
            return False
        return True


def json_tags(tags: list[str]) -> str:
    import json

    return json.dumps(tags)
