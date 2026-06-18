from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Receipt(BaseModel):
    id: str = Field(default_factory=lambda: f"rcpt_{uuid4().hex[:12]}")
    action: str
    status: str
    summary: str
    actor: str = "xv8"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
