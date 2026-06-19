import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row


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
                    project_scope TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_active ON brain_memory_records(active, soft_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_layer_type ON brain_memory_records(layer, type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_project_scope ON brain_memory_records(project_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_global_scope ON brain_memory_records(global_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_updated_at ON brain_memory_records(updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_memory_soft_deleted ON brain_memory_records(soft_deleted)")
            conn.commit()

    def status(self) -> dict[str, Any]:
        self.ensure()
        with self.connect() as conn:
            active = conn.execute("SELECT COUNT(*) AS count FROM brain_memory_records WHERE active=true AND soft_deleted=false").fetchone()["count"]
            pending = conn.execute("SELECT COUNT(*) AS count FROM brain_memory_records WHERE requires_approval=true AND approved_by_user=false AND soft_deleted=false").fetchone()["count"]
            focus = conn.execute("SELECT focus FROM brain_active_focus WHERE active=true ORDER BY updated_at DESC LIMIT 1").fetchone()
        return {"brain_ready": True, "active_memory_count": active, "pending_approval_count": pending, "active_focus": focus["focus"] if focus else ""}

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
                    linked_receipt_id, version
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,true,%s,%s,%s,%s,%s,%s,1)
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

    def list_memories(self, include_deleted: bool = False) -> list[dict[str, Any]]:
        self.ensure()
        where = "" if include_deleted else "WHERE soft_deleted=false"
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM brain_memory_records {where} ORDER BY updated_at DESC LIMIT 200").fetchall()
        return [self._decode(row) for row in rows]

    def update_memory(self, memory_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        self.ensure()
        allowed = {"title", "content", "summary", "active", "soft_deleted", "approved_by_user", "requires_approval", "project_scope", "global_scope"}
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

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        self.ensure()
        terms = self._terms(query)
        required_terms = {term for term in terms if any(char.isdigit() for char in term)}
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM brain_memory_records
                WHERE active=true AND soft_deleted=false AND approved_by_user=true AND requires_approval=false
                ORDER BY updated_at DESC
                LIMIT 200
                """
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
        return selected

    def record_event(self, memory_id: str, event_type: str, event_summary: str, source: str = "brain") -> dict[str, Any]:
        self.ensure()
        event = {"id": f"brain_evt_{uuid4().hex[:12]}", "memory_id": memory_id, "event_type": event_type, "event_summary": event_summary, "source": source, "created_at": _now()}
        safe_summary = self._redact(event_summary)
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

    def _redact(self, text: str) -> str:
        text = re.sub(r"\bgh[pousr]_[A-Za-z0-9_]+", "[redacted-token]", text, flags=re.IGNORECASE)
        text = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*", "[redacted-private-key]", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"(?i)(password|token|api[_ -]?key|secret)\s*(is|=|:)\s*\S+", r"\1 [redacted]", text)
        return text
