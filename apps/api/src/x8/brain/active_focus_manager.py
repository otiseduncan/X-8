from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from x8.brain.memory_store import BrainMemoryStore


class ActiveFocusManager:
    def __init__(self, store: BrainMemoryStore) -> None:
        self.store = store

    def set_focus(self, focus: str, session_id: str = "", project_scope: str = "") -> dict[str, Any]:
        self.store.ensure()
        now = datetime.now(timezone.utc)
        focus_id = f"brain_focus_{uuid4().hex[:12]}"
        with self.store.connect() as conn:
            conn.execute("UPDATE brain_active_focus SET active=false WHERE active=true AND project_scope=%s AND session_id=%s", (project_scope, session_id))
            conn.execute(
                "INSERT INTO brain_active_focus(id, focus, project_scope, session_id, created_at, updated_at, active) VALUES (%s,%s,%s,%s,%s,%s,true)",
                (focus_id, focus, project_scope, session_id, now, now),
            )
            conn.commit()
        self.store.record_event("", "focus_updated", f"Active focus updated: {focus}", "brain")
        return {"id": focus_id, "focus": focus, "project_scope": project_scope, "session_id": session_id, "active": True, "updated_at": now}

    def get_focus(self, session_id: str = "", project_scope: str = "") -> dict[str, Any] | None:
        self.store.ensure()
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM brain_active_focus
                WHERE active=true AND (session_id=%s OR session_id='') AND (project_scope=%s OR project_scope='')
                ORDER BY CASE WHEN session_id=%s THEN 0 ELSE 1 END, updated_at DESC
                LIMIT 1
                """,
                (session_id, project_scope, session_id),
            ).fetchone()
        return dict(row) if row else None

    def current_work_answer(self, session_id: str = "", project_scope: str = "") -> str:
        focus = self.get_focus(session_id=session_id, project_scope=project_scope)
        if not focus:
            return "I do not have an active focus saved yet."
        return f"We are currently working on: {focus['focus']}."

