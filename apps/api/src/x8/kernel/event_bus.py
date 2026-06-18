from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class KernelEvent(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    def __init__(self) -> None:
        self.events: list[KernelEvent] = []

    def emit(self, event_type: str, **payload: Any) -> None:
        safe_payload = {key: value for key, value in payload.items() if "token" not in key.lower() and "secret" not in key.lower()}
        self.events.append(KernelEvent(event_type=event_type, payload=safe_payload))

    def summary(self) -> list[str]:
        return [event.event_type for event in self.events]
