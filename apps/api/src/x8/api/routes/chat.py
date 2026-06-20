from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.chat import AttachmentReference, ChatRequest, ChatResponse, ChatRoleMessage, PromptReceipt
from x8.contracts.receipts import Receipt
from x8.brain.continuity_manager import BrainContinuityManager
from x8.brain.memory_manager import BrainMemoryManager
from x8.brain.embedding_client import OllamaEmbeddingClient
from x8.kernel.brain_context import BrainContextAssembler
from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.contracts import KernelRequest
from x8.kernel.kernel import XV8Kernel
from x8.kernel.model_router import ModelProfileManager, ModelRouter
from x8.managers.memory_manager import MemoryManager
from x8.kernel.prompt_builder import KernelPromptBuilder
from x8.managers.model_manager import OllamaAdapter
from x8.project_builder.manager import ProjectBuilderManager
from x8.brain.memory_policy import redact_secret
from x8.storage.postgres_store import PostgresStore

router = APIRouter(prefix="/api", tags=["chat"])


def _store(request: Request) -> PostgresStore:
    return PostgresStore(request.app.state.settings.database_url)


def _title(message: str) -> str:
    return message.strip().replace("\n", " ")[:80] or "XV8 session"


def _kernel(request: Request) -> XV8Kernel:
    settings = request.app.state.settings
    limits = {
        "context_max_messages": settings.context_max_messages,
        "context_max_attachment_chars": settings.context_max_attachment_chars,
        "context_max_memory_items": settings.context_max_memory_items,
        "context_max_knowledge_items": settings.context_max_knowledge_items,
    }
    brain = BrainContextAssembler(settings.knowledge_root, limits, MemoryManager(settings.memory_storage_path) if settings.memory_enabled else None)
    context = KernelContextAssembler(brain, KernelPromptBuilder())
    code_model = settings.code_model
    profiles = ModelProfileManager(
        settings.default_chat_model,
        settings.fallback_chat_model,
        code_model,
        settings.fast_model,
        settings.embedding_model,
        settings.reasoning_model,
        settings.ollama_mode,
        settings.ollama_base_url,
    )
    brain_manager = BrainMemoryManager(
        settings.database_url,
        memory_enabled=settings.brain_memory_enabled and settings.memory_enabled,
        global_enabled=settings.brain_memory_global_enabled,
        project_enabled=settings.brain_memory_project_enabled,
        session_enabled=settings.brain_memory_session_enabled,
        auto_capture_enabled=settings.memory_auto_capture_enabled,
        auto_capture_min_confidence=settings.memory_auto_capture_min_confidence,
        auto_capture_max_per_turn=settings.memory_auto_capture_max_per_turn,
        auto_capture_receipts_enabled=settings.memory_auto_capture_receipts_enabled,
        semantic_retrieval_enabled=settings.memory_semantic_retrieval_enabled,
        embedding_enabled=settings.memory_embedding_enabled,
        embedding_client=OllamaEmbeddingClient(settings.ollama_base_url, settings.embedding_model),
        embedding_model=settings.embedding_model,
        retrieval_max_results=settings.memory_retrieval_max_results,
        retrieval_min_score=settings.memory_retrieval_min_score,
    )
    continuity_manager = BrainContinuityManager(settings.database_url)
    project_builder_manager = ProjectBuilderManager(settings.workspace_root, settings.project_builder_sandbox_path)
    return XV8Kernel(context, ModelRouter(OllamaAdapter(settings.ollama_base_url), profiles), brain_manager=brain_manager, continuity_manager=continuity_manager, project_builder_manager=project_builder_manager)


def _speech_act(message: str) -> str:
    lower = message.lower()
    if lower.startswith("remember "):
        return "memory_write"
    if lower.startswith("what do you remember") or "what do you remember" in lower:
        return "memory_recall"
    if any(token in lower for token in ("do not", "no ", "only", "approve", "approved")):
        return "constrained_request"
    if any(token in lower for token in ("build", "create", "generate", "open", "run", "write", "push", "commit")):
        return "action_request"
    if "?" in message:
        return "question"
    return "statement"


def _constraints(message: str) -> list[str]:
    lower = message.lower()
    checks = {
        "preview_only": ("preview only" in lower or "do not write files" in lower),
        "sandbox_write_approved": ("approve" in lower and "sandbox" in lower),
        "no_git_commit": ("no git commit" in lower or "no commit" in lower),
        "no_push": ("no push" in lower or "do not push" in lower),
        "readme_mentioned": "readme.md" in lower,
        "manifest_mentioned": "manifest.json" in lower,
    }
    return [name for name, present in checks.items() if present]


def _memory_ids_from_receipts(receipts: list[Receipt]) -> list[str]:
    ids: list[str] = []
    for receipt in receipts:
        metadata = receipt.metadata or {}
        for key in ("memory_id", "memory_ids"):
            value = metadata.get(key)
            if isinstance(value, str):
                ids.append(value)
            elif isinstance(value, list):
                ids.extend(str(item) for item in value)
    return sorted(set(ids))


def _current_overrides(message: str) -> list[str]:
    lower = message.lower()
    overrides = []
    if "for this one" in lower or "current instruction" in lower:
        overrides.append("current_instruction_overrides_memory")
    if "i approve" in lower and "sandbox" in lower:
        overrides.append("explicit_sandbox_approval")
    return overrides


def _decision_trace(message_id: str, payload: ChatRequest, kernel_response, envelope_receipt: Receipt, extra_receipts: list[Receipt], brain_status: dict[str, object]) -> dict[str, object]:
    lane = kernel_response.decision.lane
    memory_ids = _memory_ids_from_receipts(extra_receipts)
    checked = ["model_status"]
    if lane.startswith("github_"):
        checked.append("github_ops")
    if lane.startswith("brain_") or memory_ids:
        checked.append("brain_memory")
    if lane in {"web_search", "image_generation", "artifact_preview", "project_builder"}:
        checked.append(lane)
    return {
        "message_id": message_id,
        "user_input_summary": redact_secret(payload.message.strip().replace("\n", " ")[:180]),
        "detected_speech_act": _speech_act(payload.message),
        "selected_route": lane,
        "route_confidence": kernel_response.decision.confidence,
        "input_constraints_detected": _constraints(payload.message),
        "memories_retrieved": memory_ids,
        "memories_used": memory_ids if lane.startswith("brain_") else [],
        "memories_rejected": [],
        "active_focus_used": bool(brain_status.get("active_focus")) and lane == "brain_continuity",
        "current_instruction_overrides": _current_overrides(payload.message),
        "capability_status_checked": checked,
        "action_selected": kernel_response.decision.tool_intent.name if kernel_response.decision.tool_intent else "respond",
        "safety_boundary_applied": kernel_response.decision.safety.model_dump(),
        "fallback_used": kernel_response.receipt.fallback_used,
        "fallback_reason": redact_secret(kernel_response.receipt.failure_reason),
        "final_response_type": "deterministic_or_tool_routed" if not kernel_response.receipt.failure_reason else "fallback_or_unavailable",
        "receipt_id": envelope_receipt.id,
    }


@router.post("/chat", response_model=ResultEnvelope[ChatResponse])
def chat(payload: ChatRequest, request: Request) -> ResultEnvelope[ChatResponse]:
    store = _store(request)
    session_id = store.upsert_session(payload.session_id, _title(payload.message))
    user_message_id = store.insert_message(session_id, "user", payload.message)
    attachments = []
    for reference in payload.attachments:
        row = store.get_attachment(reference.attachment_id)
        if row:
            attachment = AttachmentReference(**row)
            attachments.append(attachment)
            store.link_attachment(user_message_id, attachment.attachment_id)
    session = store.get_session(session_id)
    session_messages = session["messages"] if session else []
    kernel = _kernel(request)
    kernel_response = kernel.handle(
        KernelRequest(
            session_id=session_id,
            user_message=payload.message,
            attachments=[item.model_dump() for item in attachments],
            active_mode="assistant",
            requested_capabilities=[],
            client_state={},
            session_messages=session_messages,
        )
    )
    assistant_message_id = store.insert_message(session_id, "assistant", kernel_response.assistant_message, [card.model_dump() for card in kernel_response.cards])
    receipt = PromptReceipt(
        receipt_id=kernel_response.receipt.receipt_id,
        action_type="prompt_round_trip",
        status=kernel_response.receipt.status,
        model=kernel_response.model_used,
        limitations=kernel_response.limitations,
        created_at=kernel_response.receipt.completed_at,
    )
    store.insert_receipt(
        {
            "receipt_id": receipt.receipt_id,
            "session_id": session_id,
            "message_id": assistant_message_id,
            "action_type": receipt.action_type,
            "status": receipt.status,
            "model": receipt.model,
            "limitations": receipt.limitations,
            "metadata": {
                "user_message_id": user_message_id,
                "kernel_lane": kernel_response.decision.lane,
                "trace_summary": kernel_response.trace_summary.model_dump(),
                "context_sources": kernel_response.receipt.context_sources_used,
                "attachments": [item.attachment_id for item in attachments],
            },
            "created_at": receipt.created_at,
        }
    )
    envelope_receipt = Receipt(
        id=receipt.receipt_id,
        action=receipt.action_type,
        status=receipt.status,
        summary=f"Kernel lane {kernel_response.decision.lane} completed with status {receipt.status}.",
        metadata={"session_id": session_id, "model": receipt.model, "limitations": receipt.limitations, "kernel_lane": kernel_response.decision.lane},
    )
    brain_status = kernel.brain_manager.status() if kernel.brain_manager else {}
    trace = _decision_trace(assistant_message_id, payload, kernel_response, envelope_receipt, kernel_response.extra_receipts, brain_status)
    return ResultEnvelope(
        ok=True,
        status=receipt.status,
        message="Chat round trip completed." if receipt.status == "passed" else "The assistant model is unavailable right now.",
        data=ChatResponse(
            session_id=session_id,
            message_id=assistant_message_id,
            assistant_message=ChatRoleMessage(role="assistant", content=kernel_response.assistant_message, cards=[card.model_dump() for card in kernel_response.cards]),
            receipt=receipt,
            attachments=attachments,
            decision_trace=trace,
        ),
        receipts=[envelope_receipt, *kernel_response.extra_receipts],
    )
