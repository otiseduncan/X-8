from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

KERNEL_CONTRACT_VERSION = "kernel.v1"
CARD_CONTRACT_VERSION = "card.v1"
RECEIPT_CONTRACT_VERSION = "receipt.v1"
TOOL_CONTRACT_VERSION = "tool.v1"
CONTEXT_BUNDLE_VERSION = "context.v1"


class ResponseCard(BaseModel):
    card_contract_version: str = CARD_CONTRACT_VERSION
    type: str
    title: str
    status: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)


class KernelReceipt(BaseModel):
    receipt_contract_version: str = RECEIPT_CONTRACT_VERSION
    receipt_id: str = Field(default_factory=lambda: f"rcpt_{uuid4().hex[:12]}")
    action_type: str = "kernel.prompt_round_trip"
    kernel_lane: str
    model_selected: str = ""
    fallback_used: bool = False
    timed_out: bool = False
    timeout_seconds: float = 0.0
    failure_reason: str = ""
    context_sources_used: list[str] = Field(default_factory=list)
    attachments_used: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    status: str
    limitations: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KernelTrace(BaseModel):
    lane_selected: str
    model_selected: str = ""
    context_sources_included: list[str] = Field(default_factory=list)
    tools_requested: list[str] = Field(default_factory=list)
    final_status: str


class BrainContextBundle(BaseModel):
    context_bundle_version: str = CONTEXT_BUNDLE_VERSION
    memory: list[str] = Field(default_factory=list)
    knowledge: list[str] = Field(default_factory=list)
    verified_status: list[str] = Field(default_factory=list)
    research: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    session_context: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class KernelContext(BaseModel):
    context_bundle: BrainContextBundle
    sources_used: list[str] = Field(default_factory=list)
    prompt: str


class ModelSelection(BaseModel):
    selected_model: str = ""
    fallback_used: bool = False
    timed_out: bool = False
    timeout_seconds: float = 0.0
    model_ready: bool = False
    reason_if_unavailable: str = ""
    available_models: list[str] = Field(default_factory=list)


class KernelDecision(BaseModel):
    lane: str
    confidence: float = 0.7
    tool_intent: "ToolIntent | None" = None
    artifact_intent: "ArtifactIntent | None" = None
    safety: "SafetyDecision"


class ToolIntent(BaseModel):
    tool_contract_version: str = TOOL_CONTRACT_VERSION
    name: str
    requires_approval: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)


class ArtifactIntent(BaseModel):
    kind: str
    title: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class SafetyDecision(BaseModel):
    allowed: bool
    requires_approval: bool = False
    risk_level: str = "read_only"
    reason: str = ""


class KernelRequest(BaseModel):
    kernel_contract_version: str = KERNEL_CONTRACT_VERSION
    session_id: str | None = None
    user_message: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    active_mode: str = "assistant"
    requested_capabilities: list[str] = Field(default_factory=list)
    client_state: dict[str, Any] = Field(default_factory=dict)
    session_messages: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KernelResponse(BaseModel):
    kernel_contract_version: str = KERNEL_CONTRACT_VERSION
    session_id: str
    assistant_message: str
    cards: list[ResponseCard] = Field(default_factory=list)
    model_used: str = ""
    decision: KernelDecision
    receipt: KernelReceipt
    trace_summary: KernelTrace
    limitations: list[str] = Field(default_factory=list)


class JobRequest(BaseModel):
    tool_contract_version: str = TOOL_CONTRACT_VERSION
    job_id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:12]}")
    capability_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class JobStatus(BaseModel):
    job_id: str
    state: str
    summary: str


class JobResult(BaseModel):
    job_id: str
    state: str
    cards: list[ResponseCard] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)


class JobReceipt(BaseModel):
    receipt_contract_version: str = RECEIPT_CONTRACT_VERSION
    job_id: str
    state: str
    summary: str


KernelDecision.model_rebuild()
