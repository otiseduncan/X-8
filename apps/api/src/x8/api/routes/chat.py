from fastapi import APIRouter, Request

from x8.brain_bridge_runtime import build_bridge_kernel
from x8.contracts.base import ResultEnvelope
from x8.contracts.chat import AttachmentReference, ChatRequest, ChatResponse, ChatRoleMessage, PromptReceipt
from x8.contracts.receipts import Receipt
from x8.kernel.contracts import KernelRequest
from x8.operator_loop_proof import is_operator_loop_proof_request, run_operator_loop_proof
from x8.storage.postgres_store import PostgresStore
from x8.visual_git_proof_lab import is_visual_git_proof_lab_request, run_visual_git_proof_lab

router = APIRouter(prefix="/api", tags=["chat"])


def _store(request: Request) -> PostgresStore:
    return PostgresStore(request.app.state.settings.database_url)


def _title(message: str) -> str:
    return message.strip().replace("\n", " ")[:80] or "XV8 session"


def _normalized(message: str) -> str:
    return " ".join(message.lower().strip().split())


def _visual_push_intent(message: str) -> bool:
    text = _normalized(message)
    return any(phrase in text for phrase in ("push it", "push to repo", "push to the repo", "initialize and push", "init and push", "initialize git", "push the proof", "push proof lab"))


def _visual_repair_intent(message: str) -> bool:
    text = _normalized(message)
    return "repair" in text and any(phrase in text for phrase in ("proof", "repo", "push", "lab"))


def _visual_approval_card(action: str = "initial-push") -> dict[str, object]:
    is_repair = action == "repair-push"
    return {
        "type": "approval",
        "title": "Authorize X8 GitHub proof-lab repair push" if is_repair else "Authorize X8 GitHub proof-lab push",
        "status": "awaiting_approval",
        "summary": "Review the IDE-visible local files first, then approve this GitHub write." if not is_repair else "Review the repaired IDE-visible files first, then approve the repair push.",
        "payload": {
            "operation": "github-proof-lab",
            "repo_name": "x8-git-proof-lab",
            "owner": "otiseduncan",
            "visibility": "private",
            "project_path": "x8-git-proof-lab",
            "validation_path": "__visual_repair__" if is_repair else "x8-git-proof-lab-pull-validation",
            "github_repo": "otiseduncan/x8-git-proof-lab",
            "local_ide_workspace": "X:/xoduz-sandbox/x8-git-proof-lab",
            "cockpit_url": "http://localhost:6022",
            "actions": [
                "Use the already-written IDE-visible workspace under X:/xoduz-sandbox/x8-git-proof-lab.",
                "Do not write hidden proof files outside the visible cockpit workspace.",
                "Commit and push to https://github.com/otiseduncan/x8-git-proof-lab only after approval." if not is_repair else "Pull, repair, commit, and push to https://github.com/otiseduncan/x8-git-proof-lab only after approval.",
            ],
            "warning": "No GitHub write has run yet. Approval will authorize the visible proof-lab push." if not is_repair else "No repair push has run yet. Approval will authorize pull, repair, commit, and push.",
        },
    }


def _visual_chat_response(
    *,
    session_id: str,
    assistant_message_id: str,
    text: str,
    status: str,
    attachments: list[AttachmentReference],
    cards: list[dict[str, object]],
    receipt: PromptReceipt,
) -> ResultEnvelope[ChatResponse]:
    return ResultEnvelope(
        ok=status in {"passed", "awaiting_approval"},
        status=status,
        message=text.split("\n", 1)[0] if text else status,
        data=ChatResponse(
            session_id=session_id,
            message_id=assistant_message_id,
            assistant_message=ChatRoleMessage(role="assistant", content=text, cards=cards),
            receipt=receipt,
            attachments=attachments,
        ),
        receipts=[
            Receipt(
                id=receipt.receipt_id,
                action=receipt.action_type,
                status=receipt.status,
                summary="Visual proof lab staged for operator approval." if status == "awaiting_approval" else "Visual proof lab command executed.",
                metadata={"session_id": session_id, "visual_git_proof_lab": True, "openwebui_brain_path": False},
            )
        ],
    )


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

    if is_operator_loop_proof_request(payload.message):
        proof_result = run_operator_loop_proof(payload.message)
        assistant_message_id = store.insert_message(session_id, "assistant", proof_result.message, [])
        receipt = PromptReceipt(
            action_type="operator_loop_proof",
            status=proof_result.status,
            model="x8-operator-proof",
            limitations=proof_result.limitations,
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
                "metadata": {"user_message_id": user_message_id, "operator_loop_proof": True, "openwebui_brain_path": False},
                "created_at": receipt.created_at,
            }
        )
        envelope_receipt = Receipt(
            id=receipt.receipt_id,
            action=receipt.action_type,
            status=receipt.status,
            summary="Operator loop proof executed." if receipt.status == "passed" else "Operator loop proof failed.",
            metadata={"session_id": session_id, "operator_loop_proof": True, "openwebui_brain_path": False},
        )
        return ResultEnvelope(
            ok=receipt.status == "passed",
            status=receipt.status,
            message="Operator loop proof completed." if receipt.status == "passed" else "Operator loop proof failed.",
            data=ChatResponse(
                session_id=session_id,
                message_id=assistant_message_id,
                assistant_message=ChatRoleMessage(role="assistant", content=proof_result.message, cards=[]),
                receipt=receipt,
                attachments=attachments,
            ),
            receipts=[envelope_receipt],
        )

    if is_visual_git_proof_lab_request(payload.message) or _visual_push_intent(payload.message) or _visual_repair_intent(payload.message):
        cards: list[dict[str, object]] = []
        if _visual_push_intent(payload.message):
            message = (
                "AWAITING_APPROVAL\n"
                "visual_step: github_push_authorization_required\n"
                "repo: otiseduncan/x8-git-proof-lab\n"
                "local_ide_workspace: X:/xoduz-sandbox/x8-git-proof-lab\n"
                "cockpit_url: http://localhost:6022\n"
                "approval: Click Approve to push the IDE-visible local changes to GitHub."
            )
            status = "awaiting_approval"
            cards = [_visual_approval_card("initial-push")]
            limitations: list[str] = []
        elif _visual_repair_intent(payload.message):
            message = (
                "AWAITING_APPROVAL\n"
                "visual_step: repair_push_authorization_required\n"
                "repo: otiseduncan/x8-git-proof-lab\n"
                "local_ide_workspace: X:/xoduz-sandbox/x8-git-proof-lab\n"
                "cockpit_url: http://localhost:6022\n"
                "approval: Click Approve to pull, repair, commit, and push the repair."
            )
            status = "awaiting_approval"
            cards = [_visual_approval_card("repair-push")]
            limitations = []
        else:
            result = run_visual_git_proof_lab(payload.message)
            message = result.message
            status = result.status
            limitations = result.limitations
            if status == "awaiting_approval":
                cards = [_visual_approval_card("initial-push")]
        assistant_message_id = store.insert_message(session_id, "assistant", message, cards)
        receipt = PromptReceipt(
            action_type="visual_git_proof_lab",
            status=status,
            model="x8-visual-proof-lab",
            limitations=limitations,
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
                "metadata": {"user_message_id": user_message_id, "visual_git_proof_lab": True, "openwebui_brain_path": False},
                "created_at": receipt.created_at,
            }
        )
        return _visual_chat_response(
            session_id=session_id,
            assistant_message_id=assistant_message_id,
            text=message,
            status=status,
            attachments=attachments,
            cards=cards,
            receipt=receipt,
        )

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
