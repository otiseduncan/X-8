import json
import re
import hashlib
import math
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from x8.brain.memory_policy import redact_secret


def _dsn(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BrainMemoryStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connect(self):
        with psycopg.connect(_dsn(self.database_url), row_factory=dict_row, connect_timeout=5) as conn:
            yield conn

    def ensure(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_memory_records (
                    id TEXT PRIMARY KEY,
                    layer TEXT NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'user_explicit',
                    source_turn_id TEXT NOT NULL DEFAULT '',
                    source_tool TEXT NOT NULL DEFAULT '',
                    provenance TEXT NOT NULL DEFAULT '',
                    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.8,
                    sensitivity TEXT NOT NULL DEFAULT 'low',
                    retention_policy TEXT NOT NULL DEFAULT 'until_deleted',
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    last_used_at TIMESTAMPTZ,
                    expires_at TIMESTAMPTZ,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    soft_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    user_editable BOOLEAN NOT NULL DEFAULT TRUE,
                    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
                    approved_by_user BOOLEAN NOT NULL DEFAULT TRUE,
                    tags TEXT NOT NULL DEFAULT '[]',
                    project_scope TEXT NOT NULL DEFAULT '',
                    global_scope BOOLEAN NOT NULL DEFAULT TRUE,
                    session_scope TEXT NOT NULL DEFAULT '',
                    linked_receipt_id TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_memory_events (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT,
                    event_type TEXT NOT NULL,
                    event_summary TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'brain',
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_active_focus (
                    id TEXT PRIMARY KEY,
                    focus TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'user_explicit',
                    project_scope TEXT NOT NULL DEFAULT '',
                    session_scope TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_memory_retrievals (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    selected_ids TEXT NOT NULL DEFAULT '[]',
                    candidate_count INTEGER NOT NULL DEFAULT 0,
                    injected_count INTEGER NOT NULL DEFAULT 0,
                    retrieval_mode TEXT NOT NULL DEFAULT 'none',
                    scores TEXT NOT NULL DEFAULT '[]',
                    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
                    fallback_reason TEXT NOT NULL DEFAULT '',
                    embedding_available BOOLEAN NOT NULL DEFAULT FALSE,
                    embedding_model TEXT NOT NULL DEFAULT '',
                    semantic_index_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_memory_embeddings (
                    memory_id TEXT PRIMARY KEY,
                    embedding_json TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    vector_dimension INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_memory_candidates (
                    id TEXT PRIMARY KEY,
                    source_text_redacted TEXT NOT NULL DEFAULT '',
                    suggested_title TEXT NOT NULL DEFAULT '',
                    suggested_content TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    layer TEXT NOT NULL DEFAULT '',
                    type TEXT NOT NULL DEFAULT '',
                    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    sensitivity TEXT NOT NULL DEFAULT 'low',
                    scope TEXT NOT NULL DEFAULT 'global',
                    reason TEXT NOT NULL DEFAULT '',
                    decision TEXT NOT NULL DEFAULT 'ignored',
                    source_turn_id TEXT NOT NULL DEFAULT '',
                    source_tool TEXT NOT NULL DEFAULT '',
                    project_scope TEXT NOT NULL DEFAULT '',
                    session_scope TEXT NOT NULL DEFAULT '',
                    global_scope BOOLEAN NOT NULL DEFAULT TRUE,
                    linked_memory_id TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_runtime_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute("ALTER TABLE brain_memory_records ADD COLUMN IF NOT EXISTS session_scope TEXT NOT NULL DEFAULT ''")
            conn.execute("ALTER TABLE brain_active_focus ADD COLUMN IF NOT EXISTS summary TEXT NOT NULL DEFAULT ''")
            conn.execute("ALTER TABLE brain_active_focus ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'user_explicit'")
            conn.execute("ALTER TABLE brain_active_focus ADD COLUMN IF NOT EXISTS session_scope TEXT NOT NULL DEFAULT ''")
            conn.execute("ALTER TABLE brain_memory_retrievals ADD COLUMN IF NOT EXISTS retrieval_mode TEXT NOT NULL DEFAULT 'none'")
            conn.execute("ALTER TABLE brain_memory_retrievals ADD COLUMN IF NOT EXISTS scores TEXT NOT NULL DEFAULT '[]'")
            conn.execute("ALTER TABLE brain_memory_retrievals ADD COLUMN IF NOT EXISTS fallback_used BOOLEAN NOT NULL DEFAULT FALSE")
            conn.execute("ALTER TABLE brain_memory_retrievals ADD COLUMN IF NOT EXISTS fallback_reason TEXT NOT NULL DEFAULT ''")
            conn.execute("ALTER TABLE brain_memory_retrievals ADD COLUMN IF NOT EXISTS embedding_available BOOLEAN NOT NULL DEFAULT FALSE")
            conn.execute("ALTER TABLE brain_memory_retrievals ADD COLUMN IF NOT EXISTS embedding_model TEXT NOT NULL DEFAULT ''")
            conn.execute("ALTER TABLE brain_memory_retrievals ADD COLUMN IF NOT EXISTS semantic_index_count INTEGER NOT NULL DEFAULT 0")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_active ON brain_memory_records(active, soft_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_layer_type ON brain_memory_records(layer, type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_project_scope ON brain_memory_records(project_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_session_scope ON brain_memory_records(session_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_global_scope ON brain_memory_records(global_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_updated_at ON brain_memory_records(updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_soft_deleted ON brain_memory_records(soft_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_focus_session_scope ON brain_active_focus(session_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_focus_project_scope ON brain_active_focus(project_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_retrieval_created_at ON brain_memory_retrievals(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_embedding_active ON brain_memory_embeddings(active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_embedding_model ON brain_memory_embeddings(embedding_model)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_candidate_decision ON brain_memory_candidates(decision, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_candidate_created_at ON brain_memory_candidates(created_at DESC)")
            conn.commit()

    def status(self) -> dict[str, Any]:
        self.ensure()
        with self.connect() as conn:
            active = conn.execute("SELECT COUNT(*) AS count FROM brain_memory_records WHERE active=true AND soft_deleted=false").fetchone()["count"]
            pending = conn.execute("SELECT COUNT(*) AS count FROM brain_memory_records WHERE requires_approval=true AND approved_by_user=false AND soft_deleted=false").fetchone()["count"]
            focus = conn.execute("SELECT focus FROM brain_active_focus WHERE active=true ORDER BY updated_at DESC LIMIT 1").fetchone()
            last_event = conn.execute("SELECT * FROM brain_memory_events ORDER BY created_at DESC LIMIT 1").fetchone()
            retrieval = conn.execute("SELECT * FROM brain_memory_retrievals ORDER BY created_at DESC LIMIT 1").fetchone()
            indexed = conn.execute("SELECT COUNT(*) AS count FROM brain_memory_embeddings WHERE active=true").fetchone()["count"]
            embedding_event = conn.execute("SELECT * FROM brain_memory_events WHERE event_type LIKE 'embedding_%' ORDER BY created_at DESC LIMIT 1").fetchone()
            latest_auto = conn.execute("SELECT * FROM brain_memory_candidates WHERE decision IN ('auto_save','pending_approval','blocked','duplicate','correction') ORDER BY created_at DESC LIMIT 1").fetchone()
            latest_noise = conn.execute("SELECT * FROM brain_memory_candidates WHERE decision IN ('ignored','blocked') ORDER BY created_at DESC LIMIT 1").fetchone()
        latest_retrieval = dict(retrieval) if retrieval else None
        if latest_retrieval:
            latest_retrieval["selected_ids"] = json.loads(latest_retrieval.get("selected_ids") or "[]")
            latest_retrieval["scores"] = json.loads(latest_retrieval.get("scores") or "[]")
        return {
            "brain_ready": True,
            "active_memory_count": active,
            "pending_approval_count": pending,
            "active_focus": focus["focus"] if focus else "",
            "last_memory_event": dict(last_event) if last_event else None,
            "latest_retrieval": latest_retrieval,
            "indexed_memory_count": indexed,
            "last_embedding_event": dict(embedding_event) if embedding_event else None,
            "latest_auto_capture_event": dict(latest_auto) if latest_auto else None,
            "last_ignored_or_blocked_reason": latest_noise["reason"] if latest_noise else "",
        }

    def create_memory(
        self,
        content: str,
        *,
        layer: str = "preferences",
        memory_type: str = "user_preference",
        title: str = "",
        summary: str = "",
        source: str = "user_explicit",
        source_turn_id: str = "",
        source_tool: str = "chat",
        provenance: str = "explicit_user_command",
        confidence: float = 0.9,
        sensitivity: str = "low",
        retention_policy: str = "until_deleted",
        active: bool = True,
        requires_approval: bool = False,
        approved_by_user: bool = True,
        tags: list[str] | None = None,
        project_scope: str = "",
        global_scope: bool = True,
        session_scope: str = "",
        linked_receipt_id: str = "",
    ) -> dict[str, Any]:
        self.ensure()
        memory_id = f"brain_mem_{uuid4().hex[:12]}"
        now = _now()
        clean_summary = summary or content
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO brain_memory_records(
                    id, layer, type, title, content, summary, source, source_turn_id, source_tool, provenance,
                    confidence, sensitivity, retention_policy, created_at, updated_at, active, soft_deleted,
                    user_editable, requires_approval, approved_by_user, tags, project_scope, global_scope,
                    session_scope, linked_receipt_id, version
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,true,%s,%s,%s,%s,%s,%s,%s,1)
                """,
                (
                    memory_id,
                    layer,
                    memory_type,
                    title,
                    content,
                    clean_summary,
                    source,
                    source_turn_id,
                    source_tool,
                    provenance,
                    confidence,
                    sensitivity,
                    retention_policy,
                    now,
                    now,
                    active,
                    requires_approval,
                    approved_by_user,
                    json.dumps(tags or []),
                    project_scope,
                    global_scope,
                    session_scope,
                    linked_receipt_id,
                ),
            )
            conn.commit()
        self.record_event(memory_id, "created", f"Memory created: {clean_summary[:160]}", source)
        return self.get_memory(memory_id) or {}

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        self.ensure()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM brain_memory_records WHERE id=%s", (memory_id,)).fetchone()
        return self._decode(row) if row else None

    def list_memories(self, include_deleted: bool = False, query: str = "", status_filter: str = "", layer: str = "", memory_type: str = "", project_scope: str = "", session_scope: str = "") -> list[dict[str, Any]]:
        self.ensure()
        clauses = []
        params: list[Any] = []
        if not include_deleted:
            clauses.append("soft_deleted=false")
        if layer:
            clauses.append("layer=%s")
            params.append(layer)
        if memory_type:
            clauses.append("type=%s")
            params.append(memory_type)
        if project_scope:
            clauses.append("project_scope=%s")
            params.append(project_scope)
        if session_scope:
            clauses.append("session_scope=%s")
            params.append(session_scope)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM brain_memory_records {where} ORDER BY updated_at DESC LIMIT 300", params).fetchall()
        items = [self._decode(row) for row in rows]
        if status_filter == "active":
            items = [item for item in items if item["active"] and not item["soft_deleted"] and item["approved_by_user"] and not item["requires_approval"]]
        elif status_filter in {"pending", "approval_required"}:
            items = [item for item in items if item["requires_approval"] and not item["approved_by_user"] and not item["soft_deleted"]]
        elif status_filter in {"deleted", "inactive"}:
            items = [item for item in self.list_memories(include_deleted=True) if item["soft_deleted"] or not item["active"]]
        if query:
            terms = self._terms(query)
            items = [item for item in items if terms <= self._terms(f"{item.get('title', '')} {item.get('summary', '')} {item.get('content', '')} {' '.join(item.get('tags', []))}")]
        return items

    def list_events(self, memory_id: str = "", event_type: str = "") -> list[dict[str, Any]]:
        self.ensure()
        clauses = []
        params: list[Any] = []
        if memory_id:
            clauses.append("memory_id=%s")
            params.append(memory_id)
        if event_type:
            clauses.append("event_type=%s")
            params.append(event_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM brain_memory_events {where} ORDER BY created_at DESC LIMIT 200", params).fetchall()
        return [dict(row) for row in rows]

    def record_candidate(self, candidate: dict[str, Any], *, decision: str, reason: str = "", linked_memory_id: str = "") -> dict[str, Any]:
        self.ensure()
        now = _now()
        candidate_id = str(candidate.get("candidate_id") or f"brain_cand_{uuid4().hex[:12]}")
        clean_source = redact_secret(str(candidate.get("source_text_redacted") or ""))
        clean_content = redact_secret(str(candidate.get("suggested_content") or ""))
        clean_summary = redact_secret(str(candidate.get("summary") or clean_content))
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO brain_memory_candidates(
                    id, source_text_redacted, suggested_title, suggested_content, summary, layer, type,
                    confidence, sensitivity, scope, reason, decision, source_turn_id, source_tool,
                    project_scope, session_scope, global_scope, linked_memory_id, created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    candidate_id,
                    clean_source,
                    redact_secret(str(candidate.get("suggested_title") or ""))[:120],
                    clean_content,
                    clean_summary,
                    str(candidate.get("layer") or ""),
                    str(candidate.get("type") or ""),
                    float(candidate.get("confidence") or 0.0),
                    str(candidate.get("sensitivity") or "low"),
                    str(candidate.get("scope") or "global"),
                    redact_secret(reason or str(candidate.get("reason") or "")),
                    decision,
                    str(candidate.get("source_turn_id") or ""),
                    str(candidate.get("source_tool") or ""),
                    str(candidate.get("project_scope") or ""),
                    str(candidate.get("session_scope") or ""),
                    bool(candidate.get("global_scope", True)),
                    linked_memory_id,
                    now,
                ),
            )
            conn.commit()
        return self.get_candidate(candidate_id) or {}

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        self.ensure()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM brain_memory_candidates WHERE id=%s", (candidate_id,)).fetchone()
        return dict(row) if row else None

    def list_candidates(self, decision: str = "", query: str = "", limit: int = 200) -> list[dict[str, Any]]:
        self.ensure()
        clauses = []
        params: list[Any] = []
        if decision:
            clauses.append("decision=%s")
            params.append(decision)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM brain_memory_candidates {where} ORDER BY created_at DESC LIMIT %s", [*params, limit]).fetchall()
        items = [dict(row) for row in rows]
        if query:
            terms = self._terms(query)
            items = [item for item in items if terms <= self._terms(f"{item.get('suggested_title', '')} {item.get('summary', '')} {item.get('source_text_redacted', '')}")]
        return items

    def update_memory(self, memory_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        self.ensure()
        allowed = {"title", "content", "summary", "tags", "active", "soft_deleted", "approved_by_user", "requires_approval", "project_scope", "global_scope", "session_scope"}
        pairs = [(key, value) for key, value in patch.items() if key in allowed]
        if not pairs:
            return self.get_memory(memory_id)
        assignments = ", ".join(f"{key}=%s" for key, _ in pairs)
        values = [value for _, value in pairs]
        values.extend([_now(), memory_id])
        with self.connect() as conn:
            conn.execute(f"UPDATE brain_memory_records SET {assignments}, updated_at=%s, version=version+1 WHERE id=%s", values)
            conn.commit()
        self.record_event(memory_id, "updated", "Memory updated.", "brain")
        return self.get_memory(memory_id)

    def soft_delete_memory(self, memory_id: str, source: str = "brain") -> dict[str, Any] | None:
        memory = self.update_memory(memory_id, {"active": False, "soft_deleted": True})
        if memory:
            self.deactivate_embedding(memory_id, "embedding_deactivated")
            self.record_event(memory_id, "soft_deleted", f"Memory forgotten: {memory.get('summary') or memory.get('content')}", source)
        return memory

    def find_duplicate_memory(self, summary: str, layer: str = "", memory_type: str = "", project_scope: str = "", session_scope: str = "") -> dict[str, Any] | None:
        terms = self._terms(summary)
        if not terms:
            return None
        for item in self.list_memories(include_deleted=False, layer=layer if layer != "active_work" else "", memory_type="" if memory_type in {"correction", "active_work_context"} else memory_type, project_scope=project_scope, session_scope=session_scope):
            item_terms = self._terms(f"{item.get('title', '')} {item.get('summary', '')} {item.get('content', '')}")
            if terms == item_terms or terms <= item_terms or item_terms <= terms:
                return item
        return None

    def find_correction_target(self, summary: str, project_scope: str = "", session_scope: str = "") -> dict[str, Any] | None:
        terms = self._terms(summary)
        marker_terms = {term for term in terms if any(char.isdigit() for char in term)}
        candidates = self.list_memories(include_deleted=False, layer="preferences", project_scope=project_scope, session_scope=session_scope)
        for item in candidates:
            item_terms = self._terms(f"{item.get('title', '')} {item.get('summary', '')} {item.get('content', '')}")
            if marker_terms and marker_terms & item_terms:
                return item
        if "answer" in terms or "direct" in terms or "short" in terms:
            for item in candidates:
                haystack = f"{item.get('title', '')} {item.get('summary', '')} {item.get('content', '')}".lower()
                if "answer" in haystack or "direct" in haystack or "senior-engineer" in haystack:
                    return item
        return None

    def touch_memory(self, memory_id: str, event_type: str, summary: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            conn.execute("UPDATE brain_memory_records SET last_used_at=%s, updated_at=%s WHERE id=%s", (_now(), _now(), memory_id))
            conn.commit()
        memory = self.get_memory(memory_id)
        if memory:
            self.record_event(memory_id, event_type, summary, "brain")
        return memory

    def runtime_setting(self, key: str, default: str = "") -> str:
        self.ensure()
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM brain_runtime_settings WHERE key=%s", (key,)).fetchone()
        return row["value"] if row else default

    def set_runtime_setting(self, key: str, value: str) -> dict[str, Any]:
        self.ensure()
        now = _now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO brain_runtime_settings(key, value, updated_at) VALUES (%s,%s,%s)
                ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at
                """,
                (key, value, now),
            )
            conn.commit()
        return {"key": key, "value": value, "updated_at": now}

    def find_forget_target(self, query: str) -> dict[str, Any] | None:
        matches = self.search(query, limit=1)
        return matches[0] if matches else None

    def search(self, query: str, limit: int = 5, project_scope: str = "", session_scope: str = "") -> list[dict[str, Any]]:
        selected, _proof = self.keyword_search_with_proof(query, limit=limit, project_scope=project_scope, session_scope=session_scope)
        return selected

    def keyword_search_with_proof(self, query: str, limit: int = 5, project_scope: str = "", session_scope: str = "", record: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self.ensure()
        terms = self._terms(query)
        required_terms = {term for term in terms if any(char.isdigit() for char in term)}
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM brain_memory_records
                WHERE active=true AND soft_deleted=false AND approved_by_user=true AND requires_approval=false
                AND (global_scope=true OR project_scope=%s OR session_scope=%s)
                ORDER BY updated_at DESC
                LIMIT 200
                """,
                (project_scope, session_scope),
            ).fetchall()
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            item = self._decode(row)
            haystack = f"{item['title']} {item['content']} {item['summary']} {' '.join(item['tags'])}".lower()
            if required_terms and not required_terms <= set(re.findall(r"[a-z0-9_-]+", haystack)):
                continue
            hits = sum(1 for term in terms if term in haystack)
            if "answer" in terms and ("prefer" in haystack or "senior-engineer" in haystack):
                hits += 2
            if "prefer" in terms and "prefer" in haystack:
                hits += 2
            if hits:
                scored.append((hits * float(item.get("confidence") or 0.8), item))
        sorted_scored = sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]
        selected = [item for _, item in sorted_scored]
        if selected:
            ids = [item["id"] for item in selected]
            with self.connect() as conn:
                conn.execute("UPDATE brain_memory_records SET last_used_at=%s WHERE id = ANY(%s)", (_now(), ids))
                conn.commit()
        proof = self.retrieval_proof(
            retrieval_mode="keyword" if selected else "none",
            selected=selected,
            scores=[score for score, _ in sorted_scored],
            fallback_used=False,
            fallback_reason="",
            embedding_available=False,
            embedding_model="",
            semantic_index_count=self.semantic_index_count(),
            candidate_count=len(scored),
        )
        if record:
            self.record_retrieval(query, selected, proof)
        return selected, proof

    def record_retrieval(self, query: str, selected: list[dict[str, Any]], proof: dict[str, Any] | None = None, candidate_count: int = 0) -> None:
        self.ensure()
        proof = proof or self.retrieval_proof(retrieval_mode="keyword" if selected else "none", selected=selected, candidate_count=candidate_count)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO brain_memory_retrievals(
                    id, query, selected_ids, candidate_count, injected_count, retrieval_mode, scores,
                    fallback_used, fallback_reason, embedding_available, embedding_model, semantic_index_count, created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    f"brain_ret_{uuid4().hex[:12]}",
                    query,
                    json.dumps([item["id"] for item in selected]),
                    int(proof.get("candidate_count") or candidate_count),
                    len(selected),
                    str(proof.get("retrieval_mode") or "none"),
                    json.dumps(proof.get("scores") or []),
                    bool(proof.get("fallback_used", False)),
                    redact_secret(str(proof.get("fallback_reason") or "")),
                    bool(proof.get("embedding_available", False)),
                    str(proof.get("embedding_model") or ""),
                    int(proof.get("semantic_index_count") or 0),
                    _now(),
                ),
            )
            conn.commit()

    def upsert_embedding(self, memory: dict[str, Any], vector: list[float], model: str) -> dict[str, Any]:
        self.ensure()
        memory_id = str(memory["id"])
        now = _now()
        content_hash = self.embedding_content_hash(memory)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO brain_memory_embeddings(memory_id, embedding_json, embedding_model, vector_dimension, content_hash, active, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,true,%s,%s)
                ON CONFLICT (memory_id) DO UPDATE SET
                    embedding_json=EXCLUDED.embedding_json,
                    embedding_model=EXCLUDED.embedding_model,
                    vector_dimension=EXCLUDED.vector_dimension,
                    content_hash=EXCLUDED.content_hash,
                    active=true,
                    updated_at=EXCLUDED.updated_at
                """,
                (memory_id, json.dumps(vector), model, len(vector), content_hash, now, now),
            )
            conn.commit()
        self.record_event(memory_id, "embedding_indexed", f"Memory embedding indexed with {model}.", "brain")
        return {"memory_id": memory_id, "embedding_model": model, "vector_dimension": len(vector), "content_hash": content_hash, "active": True}

    def deactivate_embedding(self, memory_id: str, event_type: str = "embedding_deactivated") -> None:
        self.ensure()
        with self.connect() as conn:
            conn.execute("UPDATE brain_memory_embeddings SET active=false, updated_at=%s WHERE memory_id=%s", (_now(), memory_id))
            conn.commit()
        self.record_event(memory_id, event_type, "Memory embedding deactivated.", "brain")

    def embedding_for(self, memory_id: str) -> dict[str, Any] | None:
        self.ensure()
        with self.connect() as conn:
            row = conn.execute("SELECT memory_id, embedding_model, vector_dimension, content_hash, active, created_at, updated_at FROM brain_memory_embeddings WHERE memory_id=%s", (memory_id,)).fetchone()
        return dict(row) if row else None

    def semantic_index_count(self) -> int:
        self.ensure()
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) AS count FROM brain_memory_embeddings WHERE active=true").fetchone()["count"])

    def indexable_memories(self) -> list[dict[str, Any]]:
        return [item for item in self.list_memories(include_deleted=False, status_filter="active") if self.is_indexable_memory(item)]

    def is_indexable_memory(self, memory: dict[str, Any]) -> bool:
        text = f"{memory.get('title', '')} {memory.get('summary', '')} {memory.get('content', '')}"
        return bool(memory.get("active") and not memory.get("soft_deleted") and memory.get("approved_by_user") and not memory.get("requires_approval") and "[redacted" not in text.lower())

    def embedding_text(self, memory: dict[str, Any]) -> str:
        return redact_secret(" ".join(str(memory.get(key) or "") for key in ("title", "summary", "content")).strip())

    def embedding_content_hash(self, memory: dict[str, Any]) -> str:
        return hashlib.sha256(self.embedding_text(memory).encode("utf-8")).hexdigest()

    def semantic_search(self, query_vector: list[float], limit: int = 5, min_score: float = 0.2, project_scope: str = "", session_scope: str = "") -> tuple[list[dict[str, Any]], list[float], int]:
        self.ensure()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT e.memory_id, e.embedding_json, r.*
                FROM brain_memory_embeddings e
                JOIN brain_memory_records r ON r.id=e.memory_id
                WHERE e.active=true AND r.active=true AND r.soft_deleted=false AND r.approved_by_user=true AND r.requires_approval=false
                AND (r.global_scope=true OR r.project_scope=%s OR r.session_scope=%s)
                """,
                (project_scope, session_scope),
            ).fetchall()
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            vector = json.loads(row.get("embedding_json") or "[]")
            score = cosine(query_vector, vector)
            if score >= min_score:
                record = dict(row)
                record.pop("embedding_json", None)
                scored.append((score, self._decode(record)))
        selected_pairs = sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]
        selected = [item for _score, item in selected_pairs]
        if selected:
            ids = [item["id"] for item in selected]
            with self.connect() as conn:
                conn.execute("UPDATE brain_memory_records SET last_used_at=%s WHERE id = ANY(%s)", (_now(), ids))
                conn.commit()
        return selected, [round(score, 4) for score, _ in selected_pairs], len(rows)

    def retrieval_proof(
        self,
        *,
        retrieval_mode: str,
        selected: list[dict[str, Any]],
        scores: list[float] | None = None,
        fallback_used: bool = False,
        fallback_reason: str = "",
        embedding_available: bool = False,
        embedding_model: str = "",
        semantic_index_count: int | None = None,
        candidate_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "retrieval_mode": retrieval_mode,
            "memory_ids_used": [item["id"] for item in selected],
            "scores": scores or [],
            "fallback_used": fallback_used,
            "fallback_reason": redact_secret(fallback_reason),
            "embedding_available": embedding_available,
            "embedding_model": embedding_model,
            "semantic_index_count": self.semantic_index_count() if semantic_index_count is None else semantic_index_count,
            "candidate_count": candidate_count,
        }

    def approve_memory(self, memory_id: str) -> dict[str, Any] | None:
        memory = self.update_memory(memory_id, {"active": True, "soft_deleted": False, "requires_approval": False, "approved_by_user": True})
        if memory:
            self.record_event(memory_id, "approved", f"Memory approved: {memory.get('summary') or memory.get('content')}", "brain")
        return memory

    def reject_memory(self, memory_id: str) -> dict[str, Any] | None:
        memory = self.update_memory(memory_id, {"active": False, "soft_deleted": True, "requires_approval": True, "approved_by_user": False})
        if memory:
            self.deactivate_embedding(memory_id, "embedding_deactivated")
            self.record_event(memory_id, "rejected", f"Memory rejected: {memory.get('summary') or memory.get('content')}", "brain")
        return memory

    def reactivate_memory(self, memory_id: str) -> dict[str, Any] | None:
        memory = self.update_memory(memory_id, {"active": True, "soft_deleted": False})
        if memory:
            self.record_event(memory_id, "reactivated", f"Memory reactivated: {memory.get('summary') or memory.get('content')}", "brain")
        return memory

    def record_event(self, memory_id: str, event_type: str, event_summary: str, source: str = "brain") -> dict[str, Any]:
        self.ensure()
        event = {"id": f"brain_evt_{uuid4().hex[:12]}", "memory_id": memory_id, "event_type": event_type, "event_summary": event_summary, "source": source, "created_at": _now()}
        safe_summary = redact_secret(event_summary)
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO brain_memory_events(id, memory_id, event_type, event_summary, source, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (event["id"], memory_id, event_type, safe_summary, source, event["created_at"]),
            )
            conn.commit()
        event["event_summary"] = safe_summary
        return event

    def _decode(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["tags"] = json.loads(data.get("tags") or "[]")
        return data

    def _terms(self, query: str) -> set[str]:
        raw = re.findall(r"[a-z0-9_-]+", query.lower())
        stop = {"what", "do", "you", "remember", "about", "that", "this", "the", "and", "for", "how", "like", "likes", "my", "i"}
        terms = {term.rstrip("s") for term in raw if len(term) > 2 and term not in stop}
        if "answers" in raw or "answer" in raw:
            terms.add("answer")
        if "prefer" in raw or "preference" in raw:
            terms.add("prefer")
        return terms


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
