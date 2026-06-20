from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class AttachmentReference(BaseModel):
    attachment_id: str = Field(default_factory=lambda: f"att_{uuid4().hex[:12]}")
    filename: str
    mime_type: str = "application/octet-stream"
    size_bytes: int
    status: str = "selected"
    extracted_text: str = ""
    content_extractable: bool = False
    storage_path: str | None = None


class AttachmentUploadReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"rcpt_{uuid4().hex[:12]}")
    attachment_id: str | None = None
    action_type: str = "attachment_uploaded"
    filename: str
    status: str
    summary: str
    limitations: list[str] = Field(default_factory=list)


class ChatAttachmentReference(BaseModel):
    attachment_id: str
    filename: str
    mime_type: str = "application/octet-stream"
    size_bytes: int


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    attachments: list[ChatAttachmentReference] = Field(default_factory=list)


class ChatRoleMessage(BaseModel):
    role: str
    content: str
    cards: list[dict[str, object]] = Field(default_factory=list)


class PromptReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"rcpt_{uuid4().hex[:12]}")
    action_type: str
    status: str
    model: str = ""
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    assistant_message: ChatRoleMessage
    receipt: PromptReceipt
    attachments: list[AttachmentReference] = Field(default_factory=list)
    decision_trace: dict[str, object] = Field(default_factory=dict)


class SessionSummary(BaseModel):
    session_id: str
    title: str
    updated_at: datetime


class SessionDetail(BaseModel):
    session_id: str
    title: str
    messages: list[dict[str, object]] = Field(default_factory=list)
    receipts: list[dict[str, object]] = Field(default_factory=list)


class ModelStatus(BaseModel):
    ollama_mode: str = "host_ollama_bridge"
    ollama_base_url: str = ""
    ollama_reachable: bool
    available_models: list[str] = Field(default_factory=list)
    blocked_models: list[str] = Field(default_factory=list)
    installed_but_blocked: list[str] = Field(default_factory=list)
    blocked_model_configured: list[str] = Field(default_factory=list)
    default_chat_model: str = ""
    reasoning_model: str = ""
    fallback_chat_model: str = ""
    code_model: str = ""
    embedding_model: str = ""
    selected_model: str = ""
    model_ready: bool = False
    missing_models: list[str] = Field(default_factory=list)
    last_checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    failure_reason: str = ""
    fallback_used: bool = False
    timed_out: bool = False
    timeout_seconds: float = 0.0
    reason_if_unavailable: str = ""
    health_prompt_succeeded: bool = False
    embedding_ready: bool = False
    memory_ready: bool = False
