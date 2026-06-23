from fastapi import APIRouter, Request

from x8.brain_bridge_runtime import build_bridge_kernel
from x8.contracts.base import ResultEnvelope
from x8.contracts.chat import AttachmentReference, ChatRequest, ChatResponse, ChatRoleMessage, PromptReceipt
from x8.contracts.receipts import Receipt
from x8.kernel.contracts import KernelRequest
from x8.storage.postgres_store import PostgresStore

router = APIRouter(prefix="/api", tags=["chat"])


def _store(request: Request) -> PostgresStore:
    return PostgresStore(request.app.state.settings.database_url)


def _title(message: str) -> str:
    return message.strip().replace("\n", " ")[:80] or "XV8 session"


@router.post("/chat", response_model=ResultEnvelope[ChatResponse])
def chat(payload: ChatRequest, request: Request) -> ResultEnvelope[ChatResponse]:
    store = _store(request)
    session_id = store.upsert_session(payload.session_id, _title(payload.message))
    user_message_id = store.insert_message(session_id, "user", payload.message)
    attachments: list[AttachmentReference] = []
    for reference in payload.attachments:
        row = store.get_attachment(reference.attachment_id)
        if row:
            attachment = AttachmentReference(**row)
            attachments.append(attachment)
            store.link_attachment(user_message_id, attachment.attachment_id)

    session = store.get_session(session_id)
    kernel_response = build_bridge_kernel(request).handle(
        KernelRequest(
            session_id=session_id,
            user_message=payload.message,
            attachments=[item.model_dump() for item in attachments],
            active_mode="assistant",
            requested_capabilities=[],
            client_state={},
            session_messages=session["messages"] if session else [],
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
            "metadata": {"user_message_id": user_message_id, "kernel_lane": kernel_response.decision.lane, "openwebui_brain_path": True},
            "created_at": receipt.created_at,
        }
    )
    envelope_receipt = Receipt(
        id=receipt.receipt_id,
        action=receipt.action_type,
        status=receipt.status,
        summary=f"Bridge lane {kernel_response.decision.lane} completed with status {receipt.status}.",
        metadata={"session_id": session_id, "model": receipt.model, "kernel_lane": kernel_response.decision.lane, "openwebui_brain_path": True},
    )
    return ResultEnvelope(
        ok=receipt.status == "passed",
        status=receipt.status,
        message="Chat round trip completed." if receipt.status == "passed" else "The configured brain bridge is unavailable right now.",
        data=ChatResponse(
            session_id=session_id,
            message_id=assistant_message_id,
            assistant_message=ChatRoleMessage(role="assistant", content=kernel_response.assistant_message, cards=[card.model_dump() for card in kernel_response.cards]),
            receipt=receipt,
            attachments=attachments,
        ),
        receipts=[envelope_receipt, *kernel_response.extra_receipts],
    )
