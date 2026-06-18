import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row


def _dsn(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


class PostgresStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._ready = False

    @contextmanager
    def connect(self):
        with psycopg.connect(_dsn(self.database_url), row_factory=dict_row, connect_timeout=5) as conn:
            yield conn

    def ensure(self) -> None:
        if self._ready:
            return
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    cards_json TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attachments (
                    attachment_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    storage_path TEXT,
                    extracted_text TEXT NOT NULL DEFAULT '',
                    content_extractable BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS message_attachments (
                    message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
                    attachment_id TEXT NOT NULL REFERENCES attachments(attachment_id) ON DELETE CASCADE,
                    PRIMARY KEY(message_id, attachment_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    message_id TEXT,
                    action_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    limitations_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS model_status_checks (
                    id TEXT PRIMARY KEY,
                    status_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.commit()
        self._ready = True

    def upsert_session(self, session_id: str | None, title: str) -> str:
        self.ensure()
        sid = session_id or f"sess_{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id, title, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET updated_at = EXCLUDED.updated_at
                """,
                (sid, title[:120] or "XV8 session", now, now),
            )
            conn.commit()
        return sid

    def insert_message(self, session_id: str, role: str, content: str, cards: list[dict[str, Any]] | None = None) -> str:
        self.ensure()
        message_id = f"msg_{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO messages(message_id, session_id, role, content, cards_json, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (message_id, session_id, role, content, json.dumps(cards or []), now),
            )
            conn.execute("UPDATE sessions SET updated_at=%s WHERE session_id=%s", (now, session_id))
            conn.commit()
        return message_id

    def link_attachment(self, message_id: str, attachment_id: str) -> None:
        self.ensure()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO message_attachments(message_id, attachment_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (message_id, attachment_id),
            )
            conn.commit()

    def insert_attachment(self, attachment: dict[str, Any]) -> None:
        self.ensure()
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO attachments(attachment_id, filename, mime_type, size_bytes, status, storage_path, extracted_text, content_extractable, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (attachment_id) DO UPDATE SET status=EXCLUDED.status, extracted_text=EXCLUDED.extracted_text, content_extractable=EXCLUDED.content_extractable
                """,
                (
                    attachment["attachment_id"],
                    attachment["filename"],
                    attachment["mime_type"],
                    attachment["size_bytes"],
                    attachment["status"],
                    attachment.get("storage_path"),
                    attachment.get("extracted_text", ""),
                    attachment.get("content_extractable", False),
                    now,
                ),
            )
            conn.commit()

    def get_attachment(self, attachment_id: str) -> dict[str, Any] | None:
        self.ensure()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM attachments WHERE attachment_id=%s", (attachment_id,)).fetchone()
        return dict(row) if row else None

    def insert_receipt(self, receipt: dict[str, Any]) -> None:
        self.ensure()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO receipts(receipt_id, session_id, message_id, action_type, status, model, limitations_json, metadata_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    receipt["receipt_id"],
                    receipt.get("session_id"),
                    receipt.get("message_id"),
                    receipt["action_type"],
                    receipt["status"],
                    receipt.get("model", ""),
                    json.dumps(receipt.get("limitations", [])),
                    json.dumps(receipt.get("metadata", {})),
                    receipt.get("created_at", datetime.now(timezone.utc)),
                ),
            )
            conn.commit()

    def insert_model_status(self, status: dict[str, Any]) -> None:
        self.ensure()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO model_status_checks(id, status_json, created_at) VALUES (%s,%s,%s)",
                (f"model_{uuid4().hex[:12]}", json.dumps(status, default=str), datetime.now(timezone.utc)),
            )
            conn.commit()

    def list_sessions(self) -> list[dict[str, Any]]:
        self.ensure()
        with self.connect() as conn:
            rows = conn.execute("SELECT session_id, title, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 50").fetchall()
        return [dict(row) for row in rows]

    def latest_session_id(self) -> str | None:
        sessions = self.list_sessions()
        return sessions[0]["session_id"] if sessions else None

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        self.ensure()
        with self.connect() as conn:
            session = conn.execute("SELECT * FROM sessions WHERE session_id=%s", (session_id,)).fetchone()
            if not session:
                return None
            messages = conn.execute(
                """
                SELECT m.*, COALESCE(
                    (
                        SELECT json_agg(row_to_json(a))
                        FROM message_attachments ma
                        JOIN attachments a ON a.attachment_id = ma.attachment_id
                        WHERE ma.message_id = m.message_id
                    ), '[]'::json
                ) AS attachments
                FROM messages m
                WHERE m.session_id=%s
                ORDER BY m.created_at ASC
                """,
                (session_id,),
            ).fetchall()
            receipts = conn.execute("SELECT * FROM receipts WHERE session_id=%s ORDER BY created_at DESC LIMIT 50", (session_id,)).fetchall()
        return {"session": dict(session), "messages": [dict(row) for row in messages], "receipts": [dict(row) for row in receipts]}

    def list_receipts(self) -> list[dict[str, Any]]:
        self.ensure()
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM receipts ORDER BY created_at DESC LIMIT 100").fetchall()
        return [dict(row) for row in rows]
