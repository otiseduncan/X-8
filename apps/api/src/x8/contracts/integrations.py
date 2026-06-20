from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from x8.contracts.capability import CapabilityStatus


class ToolCallRequest(BaseModel):
    tool: str
    action: str
    args: dict[str, str] = Field(default_factory=dict)
    approved: bool = False


class ToolCallResult(BaseModel):
    tool: str
    status: CapabilityStatus
    output: str
    mutated: bool = False


class IntegrationStatus(BaseModel):
    name: str
    status: CapabilityStatus
    live: bool = False
    reason: str = ""
    required_config: list[str] = Field(default_factory=list)
    safe_actions: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)
    last_checked: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    receipt: dict[str, Any] = Field(default_factory=dict)
    summary: str
    credential_required: bool = False
    approval_required: bool = True
