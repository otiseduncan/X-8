from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from x8.brain.memory_store import BrainMemoryStore


class ActiveFocusManager:
    def __init__(self, store: BrainMemoryStore) -> None:
        self.store = store

    def set_focus(self, focus: str, session_id: str = "", project_scope: str = "", session_scope: str = "", source: str = "user_explicit") -> dict[str, Any]:
        self.store.ensure()
        now = datetime.now(timezone.utc)
        focus_id = f"brain_focus_{uuid4().hex[:12]}"
        effective_session_scope = session_scope or session_id
        with self.store.connect() as conn:
            conn.execute("UPDATE brain_active_focus SET active=false WHERE active=true AND project_scope=%s AND session_scope=%s", (project_scope, effective_session_scope))
            conn.execute(
                """
                INSERT INTO brain_active_focus(id, focus, summary, source, project_scope, session_scope, session_id, created_at, updated_at, active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,true)
                """,
                (focus_id, focus, focus, source, project_scope, effective_session_scope, session_id, now, now),
            )
            conn.commit()
        self.store.record_event("", "focus_updated", f"Active focus updated: {focus}", "brain")
        return {"id": focus_id, "focus": focus, "summary": focus, "source": source, "project_scope": project_scope, "session_scope": effective_session_scope, "session_id": session_id, "active": True, "updated_at": now}

    def get_focus(self, session_id: str = "", project_scope: str = "", session_scope: str = "") -> dict[str, Any] | None:
        self.store.ensure()
        effective_session_scope = session_scope or session_id
        with self.store.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM brain_active_focus
                WHERE active=true AND (session_scope=%s OR session_scope='' OR session_id=%s OR session_id='') AND (project_scope=%s OR project_scope='')
                ORDER BY CASE WHEN session_scope=%s THEN 0 WHEN session_id=%s THEN 1 ELSE 2 END, updated_at DESC
                LIMIT 1
                """,
                (effective_session_scope, session_id, project_scope, effective_session_scope, session_id),
            ).fetchone()
        return dict(row) if row else None

    def clear_focus(self, session_id: str = "", project_scope: str = "", session_scope: str = "") -> None:
        self.store.ensure()
        effective_session_scope = session_scope or session_id
        with self.store.connect() as conn:
            conn.execute("UPDATE brain_active_focus SET active=false, updated_at=%s WHERE active=true AND project_scope=%s AND session_scope=%s", (datetime.now(timezone.utc), project_scope, effective_session_scope))
            conn.commit()
        self.store.record_event("", "focus_cleared", "Active focus cleared.", "brain")

    def current_work_answer(self, session_id: str = "", project_scope: str = "", session_scope: str = "") -> str:
        focus = self.get_focus(session_id=session_id, project_scope=project_scope, session_scope=session_scope)
        if not focus:
            return "I do not have an active focus saved yet."
        return f"We are currently working on: {focus['focus']}."
