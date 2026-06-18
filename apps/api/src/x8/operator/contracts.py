from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

OPERATOR_CONTRACT_VERSION = "operator.v1"
TOOL_CONTRACT_VERSION = "operator-tool.v1"


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    LOW_MUTATION = "low_mutation"
    NORMAL_MUTATION = "normal_mutation"
    DESTRUCTIVE = "destructive"
    EXTERNAL_SEND = "external_send"
    CREDENTIAL_SENSITIVE = "credential_sensitive"
    REMOTE_CONTROL = "remote_control"
    SYSTEM_LEVEL = "system_level"


class JobState(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    APPROVED = "approved"
    RUNNING = "running"
    OBSERVING = "observing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    EXECUTED = "executed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class OperatorBase(BaseModel):
    contract_version: str = OPERATOR_CONTRACT_VERSION
    id: str = Field(default_factory=lambda: _id("op"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "created"
    source: str = "api"
    limitations: list[str] = Field(default_factory=list)
    receipt_id: str = ""


class OperatorTaskRequest(BaseModel):
    session_id: str | None = None
    prompt: str
    action_type: str = "inspect"
    target_type: str = "workspace"
    target_identifier: str = ""
    dry_run: bool = True
    source: str = "api"


class OperatorPlanStep(OperatorBase):
    id: str = Field(default_factory=lambda: _id("step"))
    title: str
    action_type: str
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    requires_approval: bool = False


class OperatorPlan(OperatorBase):
    id: str = Field(default_factory=lambda: _id("plan"))
    task_id: str
    summary: str
    steps: list[OperatorPlanStep] = Field(default_factory=list)


class OperatorAction(OperatorBase):
    id: str = Field(default_factory=lambda: _id("act"))
    task_id: str
    action_type: str
    target_type: str = "workspace"
    target_identifier: str = ""
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    requires_approval: bool = False
    action_hash: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class OperatorTask(OperatorBase):
    id: str = Field(default_factory=lambda: _id("task"))
    session_id: str | None = None
    prompt: str
    plan: OperatorPlan | None = None
    actions: list[OperatorAction] = Field(default_factory=list)
    job_id: str = ""


class OperatorActionResult(OperatorBase):
    id: str = Field(default_factory=lambda: _id("result"))
    action_id: str
    output_summary: str = ""
    output: str = ""
    mutated: bool = False


class OperatorObservation(OperatorBase):
    id: str = Field(default_factory=lambda: _id("obs"))
    observation_type: str
    scope: str = ""
    summary: str
    content: str = ""
    truncated: bool = False


class OperatorVerification(OperatorBase):
    id: str = Field(default_factory=lambda: _id("verify"))
    task_id: str
    verified: bool = False
    summary: str = ""


class OperatorRecoveryPlan(OperatorBase):
    id: str = Field(default_factory=lambda: _id("recover"))
    task_id: str
    summary: str = "No recovery needed for mock/read-only scaffold."
    steps: list[str] = Field(default_factory=list)


class OperatorRiskAssessment(OperatorBase):
    id: str = Field(default_factory=lambda: _id("risk"))
    action_type: str
    risk_level: RiskLevel
    requires_approval: bool
    reason: str


class OperatorApprovalRequest(OperatorBase):
    id: str = Field(default_factory=lambda: _id("appr"))
    task_id: str
    action_id: str
    risk_level: RiskLevel
    action_type: str
    target_type: str
    target_identifier: str
    human_summary: str
    technical_summary: str
    before_state_summary: str = ""
    after_state_prediction: str = ""
    diff_or_preview: str = ""
    rollback_plan: str = ""
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=30))
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decided_by: str = ""
    decision: str = ""
    execution_token_hash: str
    status: str = ApprovalStatus.PENDING


class OperatorApprovalDecision(BaseModel):
    decision: str
    decided_by: str = "user_click"


class OperatorExecutionReceipt(OperatorBase):
    id: str = Field(default_factory=lambda: _id("orec"))
    task_id: str = ""
    action_id: str = ""
    action_type: str = ""
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    summary: str = ""


class OperatorAuditEvent(OperatorBase):
    id: str = Field(default_factory=lambda: _id("audit"))
    task_id: str = ""
    job_id: str = ""
    approval_id: str = ""
    event_type: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperatorJob(OperatorBase):
    id: str = Field(default_factory=lambda: _id("job"))
    task_id: str
    state: JobState = JobState.QUEUED
    summary: str = ""


class OperatorJobStatus(OperatorBase):
    id: str
    job_id: str
    task_id: str
    state: JobState
    summary: str
    approvals: list[OperatorApprovalRequest] = Field(default_factory=list)
    observations: list[OperatorObservation] = Field(default_factory=list)
    results: list[OperatorActionResult] = Field(default_factory=list)


class OperatorResourceBudget(BaseModel):
    contract_version: str = OPERATOR_CONTRACT_VERSION
    id: str = Field(default_factory=lambda: _id("budget"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"
    source: str = "settings"
    limitations: list[str] = Field(default_factory=list)
    receipt_id: str = ""
    max_runtime_seconds: int = 300
    max_output_chars: int = 6000
    max_file_bytes: int = 1000000
    max_context_chars: int = 12000
    max_parallel_jobs: int = 2
    model_timeout_seconds: int = 120
    tool_timeout_seconds: int = 60
    memory_timeout_seconds: int = 10


class OperatorCapability(OperatorBase):
    id: str = Field(default_factory=lambda: _id("cap"))
    capability_id: str
    display_name: str
    category: str
    risk_level: RiskLevel
    manager: str = ""
    adapter: str = ""
    supported_actions: list[str] = Field(default_factory=list)
    requires_credentials: bool = False
    requires_approval: bool = False
    health_check: str = "not_run"


class ToolSpec(BaseModel):
    contract_version: str = TOOL_CONTRACT_VERSION
    id: str = Field(default_factory=lambda: _id("tool"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "registered"
    source: str = "operator_registry"
    limitations: list[str] = Field(default_factory=list)
    receipt_id: str = ""
    action_type: str
    risk_level: RiskLevel
    requires_approval: bool
    requires_observation: bool = True
    supports_dry_run: bool = True
    supports_rollback: bool = False
    allowed_targets: list[str] = Field(default_factory=list)
    blocked_targets: list[str] = Field(default_factory=list)
    timeout_seconds: int = 60
    resource_budget: OperatorResourceBudget = Field(default_factory=OperatorResourceBudget)


class ToolInvocation(OperatorBase):
    id: str = Field(default_factory=lambda: _id("invoke"))
    tool_id: str
    action_type: str
    target_identifier: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False


class ToolResult(OperatorBase):
    id: str = Field(default_factory=lambda: _id("toolres"))
    invocation_id: str
    output_summary: str = ""
    output: str = ""
    mutated: bool = False
