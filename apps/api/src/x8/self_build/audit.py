from datetime import datetime, timezone
from uuid import uuid4


class SelfBuildAuditManager:
    def event(self, event_type: str, summary: str, **metadata):
        return {
            "audit_id": f"sbaud_{uuid4().hex[:12]}",
            "event_type": event_type,
            "summary": summary,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
