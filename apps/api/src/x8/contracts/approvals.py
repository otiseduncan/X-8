from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    SAFE_READ = "safe_read"
    LOW_CHANGE = "low_change"
    MEDIUM_CHANGE = "medium_change"
    DESTRUCTIVE = "destructive"
    HIGH_RISK = "high_risk"
    BLOCKED = "blocked"


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING_CLICK = "pending_click"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    BLOCKED = "blocked"


class RollbackHint(BaseModel):
    summary: str
    reversible: bool = True


class ActionIntent(BaseModel):
    action: str
    files_affected: list[str] = Field(default_factory=list)
    summary: str
    will_change_files: bool = False
    before_after_summary: str = ""
    tests_recommended: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: f"appr_{uuid4().hex[:12]}")
    action: str
    risk: RiskLevel
    intent: ActionIntent
    rollback_hint: RollbackHint
    status: ApprovalStatus = ApprovalStatus.PENDING_CLICK
    reason: str = ""
    typed_confirmation: str | None = None
    approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalDecision(BaseModel):
    approval_id: str
    approved_by_user_click: bool
    cancel_reason: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActionReceipt(BaseModel):
    approval_id: str | None = None
    status: ApprovalStatus
    receipt_id: str
    summary: str
