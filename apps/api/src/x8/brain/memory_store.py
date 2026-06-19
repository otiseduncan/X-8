import json
import re
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
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute("ALTER TABLE brain_memory_records ADD COLUMN IF NOT EXISTS session_scope TEXT NOT NULL DEFAULT ''")
            conn.execute("ALTER TABLE brain_active_focus ADD COLUMN IF NOT EXISTS summary TEXT NOT NULL DEFAULT ''")
            conn.execute("ALTER TABLE brain_active_focus ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'user_explicit'")
            conn.execute("ALTER TABLE brain_active_focus ADD COLUMN IF NOT EXISTS session_scope TEXT NOT NULL DEFAULT ''")
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
            conn.commit()

    def status(self) -> dict[str, Any]:
        self.ensure()
        with self.connect() as conn:
            active = conn.execute("SELECT COUNT(*) AS count FROM brain_memory_records WHERE active=true AND soft_deleted=false").fetchone()["count"]
            pending = conn.execute("SELECT COUNT(*) AS count FROM brain_memory_records WHERE requires_approval=true AND approved_by_user=false AND soft_deleted=false").fetchone()["count"]
            focus = conn.execute("SELECT focus FROM brain_active_focus WHERE active=true ORDER BY updated_at DESC LIMIT 1").fetchone()
            last_event = conn.execute("SELECT * FROM brain_memory_events ORDER BY created_at DESC LIMIT 1").fetchone()
            retrieval = conn.execute("SELECT * FROM brain_memory_retrievals ORDER BY created_at DESC LIMIT 1").fetchone()
        latest_retrieval = dict(retrieval) if retrieval else None
        if latest_retrieval:
            latest_retrieval["selected_ids"] = json.loads(latest_retrieval.get("selected_ids") or "[]")
        return {"brain_ready": True, "active_memory_count": active, "pending_approval_count": pending, "active_focus": focus["focus"] if focus else "", "last_memory_event": dict(last_event) if last_event else None, "latest_retrieval": latest_retrieval}

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

    def list_events(self, memory_id: str = "") -> list[dict[str, Any]]:
        self.ensure()
        where = "WHERE memory_id=%s" if memory_id else ""
        params = (memory_id,) if memory_id else ()
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM brain_memory_events {where} ORDER BY created_at DESC LIMIT 200", params).fetchall()
        return [dict(row) for row in rows]

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
            self.record_event(memory_id, "soft_deleted", f"Memory forgotten: {memory.get('summary') or memory.get('content')}", source)
        return memory

    def find_forget_target(self, query: str) -> dict[str, Any] | None:
        matches = self.search(query, limit=1)
        return matches[0] if matches else None

    def search(self, query: str, limit: int = 5, project_scope: str = "", session_scope: str = "") -> list[dict[str, Any]]:
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
        selected = [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]
        if selected:
            ids = [item["id"] for item in selected]
            with self.connect() as conn:
                conn.execute("UPDATE brain_memory_records SET last_used_at=%s WHERE id = ANY(%s)", (_now(), ids))
                conn.commit()
        self.record_retrieval(query, selected, candidate_count=len(scored))
        return selected

    def record_retrieval(self, query: str, selected: list[dict[str, Any]], candidate_count: int) -> None:
        self.ensure()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO brain_memory_retrievals(id, query, selected_ids, candidate_count, injected_count, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (f"brain_ret_{uuid4().hex[:12]}", query, json.dumps([item["id"] for item in selected]), candidate_count, len(selected), _now()),
            )
            conn.commit()

    def approve_memory(self, memory_id: str) -> dict[str, Any] | None:
        memory = self.update_memory(memory_id, {"active": True, "soft_deleted": False, "requires_approval": False, "approved_by_user": True})
        if memory:
            self.record_event(memory_id, "approved", f"Memory approved: {memory.get('summary') or memory.get('content')}", "brain")
        return memory

    def reject_memory(self, memory_id: str) -> dict[str, Any] | None:
        memory = self.update_memory(memory_id, {"active": False, "soft_deleted": True, "requires_approval": True, "approved_by_user": False})
        if memory:
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
