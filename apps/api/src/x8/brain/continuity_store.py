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


class BrainContinuityStore:
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
                CREATE TABLE IF NOT EXISTS brain_continuity_records (
                    id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    priority TEXT NOT NULL DEFAULT 'normal',
                    project_scope TEXT NOT NULL DEFAULT '',
                    session_scope TEXT NOT NULL DEFAULT '',
                    global_scope BOOLEAN NOT NULL DEFAULT TRUE,
                    source TEXT NOT NULL DEFAULT 'user_explicit',
                    provenance TEXT NOT NULL DEFAULT 'explicit_user_command',
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    last_used_at TIMESTAMPTZ,
                    linked_memory_id TEXT NOT NULL DEFAULT '',
                    linked_commit_sha TEXT NOT NULL DEFAULT '',
                    linked_validation_event TEXT NOT NULL DEFAULT '',
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    soft_deleted BOOLEAN NOT NULL DEFAULT FALSE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS brain_continuity_events (
                    id TEXT PRIMARY KEY,
                    record_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    event_summary TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'brain',
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_continuity_type_status ON brain_continuity_records(record_type, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_continuity_scope ON brain_continuity_records(project_scope, session_scope, global_scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_continuity_updated ON brain_continuity_records(updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_brain_continuity_events_created ON brain_continuity_events(created_at DESC)")
            conn.commit()

    def create_record(self, record: dict[str, Any]) -> dict[str, Any]:
        self.ensure()
        now = _now()
        record_id = str(record.get("id") or f"brain_cont_{uuid4().hex[:12]}")
        payload = {
            "id": record_id,
            "record_type": str(record.get("record_type") or "task"),
            "title": redact_secret(str(record.get("title") or record.get("summary") or ""))[:160],
            "summary": redact_secret(str(record.get("summary") or record.get("content") or "")),
            "content": redact_secret(str(record.get("content") or record.get("summary") or "")),
            "status": str(record.get("status") or "active"),
            "priority": str(record.get("priority") or "normal"),
            "project_scope": str(record.get("project_scope") or ""),
            "session_scope": str(record.get("session_scope") or ""),
            "global_scope": bool(record.get("global_scope", True)),
            "source": str(record.get("source") or "user_explicit"),
            "provenance": str(record.get("provenance") or "explicit_user_command"),
            "linked_memory_id": str(record.get("linked_memory_id") or ""),
            "linked_commit_sha": str(record.get("linked_commit_sha") or ""),
            "linked_validation_event": str(record.get("linked_validation_event") or ""),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO brain_continuity_records(
                    id, record_type, title, summary, content, status, priority, project_scope, session_scope,
                    global_scope, source, provenance, created_at, updated_at, linked_memory_id,
                    linked_commit_sha, linked_validation_event, active, soft_deleted
                )
                VALUES (%(id)s,%(record_type)s,%(title)s,%(summary)s,%(content)s,%(status)s,%(priority)s,%(project_scope)s,%(session_scope)s,
                    %(global_scope)s,%(source)s,%(provenance)s,%(created_at)s,%(updated_at)s,%(linked_memory_id)s,
                    %(linked_commit_sha)s,%(linked_validation_event)s,true,false)
                """,
                payload | {"created_at": now, "updated_at": now},
            )
            conn.commit()
        self.record_event(record_id, f"{payload['record_type']}_created", f"Continuity record saved: {payload['summary']}")
        return self.get_record(record_id) or {}

    def update_record(self, record_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        self.ensure()
        allowed = {"title", "summary", "content", "status", "priority", "project_scope", "session_scope", "global_scope", "linked_memory_id", "linked_commit_sha", "linked_validation_event", "active", "soft_deleted"}
        pairs = []
        for key, value in patch.items():
            if key not in allowed:
                continue
            if key in {"title", "summary", "content", "linked_validation_event"}:
                value = redact_secret(str(value))
            pairs.append((key, value))
        if not pairs:
            return self.get_record(record_id)
        assignments = ", ".join(f"{key}=%s" for key, _ in pairs)
        values = [value for _, value in pairs]
        values.extend([_now(), record_id])
        with self.connect() as conn:
            conn.execute(f"UPDATE brain_continuity_records SET {assignments}, updated_at=%s WHERE id=%s", values)
            conn.commit()
        self.record_event(record_id, "continuity_updated", "Continuity record updated.")
        return self.get_record(record_id)

    def soft_delete_record(self, record_id: str) -> dict[str, Any] | None:
        record = self.update_record(record_id, {"active": False, "soft_deleted": True, "status": "archived"})
        if record:
            self.record_event(record_id, "continuity_archived", f"Continuity record archived: {record.get('summary')}")
        return record

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        self.ensure()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM brain_continuity_records WHERE id=%s", (record_id,)).fetchone()
        return dict(row) if row else None

    def list_records(self, *, record_type: str = "", status: str = "", project_scope: str = "", session_scope: str = "", include_deleted: bool = False, query: str = "", limit: int = 200) -> list[dict[str, Any]]:
        self.ensure()
        clauses = []
        params: list[Any] = []
        if record_type:
            clauses.append("record_type=%s")
            params.append(record_type)
        if status:
            clauses.append("status=%s")
            params.append(status)
        if session_scope:
            clauses.append("session_scope=%s")
            params.append(session_scope)
        elif project_scope:
            clauses.append("(project_scope=%s OR global_scope=true)")
            params.append(project_scope)
        if not include_deleted:
            clauses.append("soft_deleted=false")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM brain_continuity_records {where} ORDER BY updated_at DESC LIMIT %s", [*params, limit]).fetchall()
        records = [dict(row) for row in rows]
        if query:
            terms = self._terms(query)
            records = [item for item in records if terms <= self._terms(f"{item.get('title', '')} {item.get('summary', '')} {item.get('content', '')}")]
        return records

    def latest(self, record_type: str, *, statuses: tuple[str, ...] = ("active",), project_scope: str = "", session_scope: str = "") -> dict[str, Any] | None:
        self.ensure()
        clauses = ["record_type=%s", "soft_deleted=false"]
        params: list[Any] = [record_type]
        if statuses:
            clauses.append("status = ANY(%s)")
            params.append(list(statuses))
        if session_scope:
            clauses.append("session_scope=%s")
            params.append(session_scope)
        elif project_scope:
            clauses.append("(project_scope=%s OR global_scope=true)")
            params.append(project_scope)
        with self.connect() as conn:
            row = conn.execute(f"SELECT * FROM brain_continuity_records WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT 1", params).fetchone()
            if row:
                conn.execute("UPDATE brain_continuity_records SET last_used_at=%s WHERE id=%s", (_now(), row["id"]))
                conn.commit()
        return dict(row) if row else None

    def upsert_singleton(self, record_type: str, summary: str, **kwargs: Any) -> dict[str, Any]:
        existing = self.latest(record_type, statuses=("active",), project_scope=str(kwargs.get("project_scope") or ""), session_scope=str(kwargs.get("session_scope") or ""))
        patch = {"title": kwargs.get("title") or summary[:120], "summary": summary, "content": kwargs.get("content") or summary, "status": kwargs.get("status") or "active", "priority": kwargs.get("priority") or "normal"}
        if existing:
            return self.update_record(existing["id"], patch) or existing
        return self.create_record({"record_type": record_type, **patch, **kwargs})

    def record_event(self, record_id: str, event_type: str, event_summary: str, source: str = "brain") -> dict[str, Any]:
        self.ensure()
        event = {"id": f"brain_cont_evt_{uuid4().hex[:12]}", "record_id": record_id, "event_type": event_type, "event_summary": redact_secret(event_summary), "source": source, "created_at": _now()}
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO brain_continuity_events(id, record_id, event_type, event_summary, source, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (event["id"], record_id, event_type, event["event_summary"], source, event["created_at"]),
            )
            conn.commit()
        return event

    def list_events(self, record_id: str = "", event_type: str = "", limit: int = 100) -> list[dict[str, Any]]:
        self.ensure()
        clauses = []
        params: list[Any] = []
        if record_id:
            clauses.append("record_id=%s")
            params.append(record_id)
        if event_type:
            clauses.append("event_type=%s")
            params.append(event_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM brain_continuity_events {where} ORDER BY created_at DESC LIMIT %s", [*params, limit]).fetchall()
        return [dict(row) for row in rows]

    def _terms(self, query: str) -> set[str]:
        return {term for term in re.findall(r"[a-z0-9_-]+", query.lower()) if len(term) > 2}
