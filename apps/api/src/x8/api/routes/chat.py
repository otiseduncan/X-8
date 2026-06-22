import json
import re

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
from x8.managers.workspace_manager import WorkspaceManager
from x8.storage.postgres_store import PostgresStore

router = APIRouter(prefix="/api", tags=["chat"])
SANDBOX_PROJECT_RE = re.compile(r"create\s+a\s+sandbox\s+project\s+called\s+([a-zA-Z0-9_-]+)", re.IGNORECASE)
DATE_SAVED_RE = re.compile(r'"dateSaved"\s*:\s*"([^"]+)"')
ESCAPE_TARGET_RE = re.compile(r"(?:^|\n)\s*((?:\.\.[/\\].+)|(?:[a-zA-Z]:[/\\].+))")


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
    return XV8Kernel(context, ModelRouter(OllamaAdapter(settings.ollama_base_url), profiles), brain_manager=brain_manager, continuity_manager=continuity_manager)


def _workspace(request: Request) -> WorkspaceManager:
    return WorkspaceManager(request.app.state.settings.workspace_root)


def _host_sandbox_root(request: Request) -> str:
    settings = request.app.state.settings
    return settings.projects_host_root or settings.workspace_host_root or "UNSET"


def _build_preview_proof_files(project: str, date_saved: str) -> dict[str, str]:
    data = {
        "project": project,
        "sandboxWrite": True,
        "dateSaved": date_saved,
    }
    return {
        f"{project}/index.html": """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Cockpit Preview Proof</title>
    <link rel=\"stylesheet\" href=\"style.css\" />
  </head>
  <body>
    <main class=\"proof-card\">
      <p class=\"eyebrow\">X8 Sandbox Write Validation</p>
      <h1>Cockpit Preview Verified</h1>
      <p id=\"js-proof\">Waiting for sandbox JavaScript...</p>
    </main>
    <script src=\"app.js\"></script>
  </body>
</html>
""",
        f"{project}/style.css": """body {
  min-height: 100vh;
  margin: 0;
  display: grid;
  place-items: center;
  background: radial-gradient(circle at top, #123042, #05070b 64%);
  color: #e5f7ff;
  font-family: Inter, system-ui, sans-serif;
}

.proof-card {
  width: min(720px, calc(100vw - 48px));
  border: 1px solid #00d4ff;
  border-radius: 24px;
  padding: 36px;
  background: rgba(8, 16, 28, 0.88);
  box-shadow: 0 24px 80px rgba(0, 212, 255, 0.18);
}

.eyebrow {
  color: #00d4ff;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

h1 {
  margin: 0 0 16px;
  font-size: clamp(2.4rem, 7vw, 5.5rem);
}

#js-proof {
  color: #b8f3ff;
  font-size: 1.25rem;
}
""",
        f"{project}/app.js": """const proof = document.querySelector('#js-proof');
if (proof) {
  proof.textContent = 'JavaScript loaded from sandbox.';
}
""",
        f"{project}/README.md": f"""# {project}

Cockpit Preview Verified

This project was created through the X operator chat deterministic sandbox bridge.

- Sandbox write: true
- dateSaved: {date_saved}
- Preview target: `index.html`
""",
        f"{project}/data.json": json.dumps(data, indent=2) + "\n",
    }


def _chat_result(
    *,
    store: PostgresStore,
    session_id: str,
    user_message_id: str,
    content: str,
    cards: list[dict[str, object]],
    action_type: str,
    status: str = "passed",
    model: str = "deterministic-sandbox-bridge",
    limitations: list[str] | None = None,
    attachments: list[AttachmentReference] | None = None,
) -> ResultEnvelope[ChatResponse]:
    limitations = limitations or []
    attachments = attachments or []
    assistant_message_id = store.insert_message(session_id, "assistant", content, cards)
    receipt = PromptReceipt(action_type=action_type, status=status, model=model, limitations=limitations)
    store.insert_receipt(
        {
            "receipt_id": receipt.receipt_id,
            "session_id": session_id,
            "message_id": assistant_message_id,
            "action_type": receipt.action_type,
            "status": receipt.status,
            "model": receipt.model,
            "limitations": receipt.limitations,
            "metadata": {"user_message_id": user_message_id, "deterministic": True},
            "created_at": receipt.created_at,
        }
    )
    envelope_receipt = Receipt(
        id=receipt.receipt_id,
        action=receipt.action_type,
        status=receipt.status,
        summary=content.splitlines()[0] if content else "Deterministic chat action completed.",
        metadata={"session_id": session_id, "model": receipt.model, "limitations": receipt.limitations},
    )
    return ResultEnvelope(
        ok=status == "passed",
        status=status,
        message="Chat deterministic sandbox action completed." if status == "passed" else "Chat deterministic sandbox action failed.",
        data=ChatResponse(
            session_id=session_id,
            message_id=assistant_message_id,
            assistant_message=ChatRoleMessage(role="assistant", content=content, cards=cards),
            receipt=receipt,
            attachments=attachments,
        ),
        receipts=[envelope_receipt],
    )


def _handle_sandbox_project_command(payload: ChatRequest, request: Request, store: PostgresStore, session_id: str, user_message_id: str, attachments: list[AttachmentReference]) -> ResultEnvelope[ChatResponse] | None:
    match = SANDBOX_PROJECT_RE.search(payload.message)
    lower = payload.message.lower()
    if not match or "index.html" not in lower or "data.json" not in lower:
        return None
    project = match.group(1).strip()
    date_match = DATE_SAVED_RE.search(payload.message)
    date_saved = date_match.group(1) if date_match else "2026-06-22"
    manager = _workspace(request)
    requested_files = _build_preview_proof_files(project, date_saved)
    writes = []
    verification_failures = []

    for path, expected_content in requested_files.items():
        try:
            write = manager.write_file(path, expected_content, overwrite=True)
            readback = manager.read_file(path, max_chars=len(expected_content) + 1000)
            verified = readback.content == expected_content
            write_payload = write.model_dump()
            write_payload["verified"] = verified
            write_payload["readback_line_count"] = readback.line_count
            writes.append(write_payload)
            if not verified:
                verification_failures.append(f"{path}: readback mismatch")
        except Exception as exc:
            verification_failures.append(f"{path}: {exc}")

    if verification_failures:
        content = (
            f"Sandbox project write FAILED: {project}\n\n"
            f"Container sandbox root: {manager.root}\n"
            f"Configured host sandbox root: {_host_sandbox_root(request)}\n\n"
            "No success receipt was issued because these files were not verified on disk:\n"
            + "\n".join(f"- {failure}" for failure in verification_failures)
        )
        return _chat_result(
            store=store,
            session_id=session_id,
            user_message_id=user_message_id,
            content=content,
            cards=[{"type": "receipt", "title": "Sandbox project write failed", "status": "failed", "payload": {"project": project, "failures": verification_failures, "files": writes}}],
            action_type="sandbox_project_create",
            status="failed",
            attachments=attachments,
        )

    created_paths = "\n".join(f"- {item['path']} -> {item['absolute_path']} [verified]" for item in writes)
    content = (
        f"Sandbox project created and verified: {project}\n\n"
        f"Container sandbox root: {writes[0]['sandbox_root']}\n"
        f"Configured host sandbox root: {_host_sandbox_root(request)}\n\n"
        "Created and read back from disk:\n"
        f"{created_paths}\n\n"
        f"Preview path: {project}/index.html\n"
        f"dateSaved persisted: {date_saved}\n\n"
        "Refresh the cockpit file tree and open the project folder. If the configured host sandbox root is not X:/xoduz-sandbox, fix X8_PROJECTS_HOST_ROOT before trusting this proof."
    )
    cards = [
        {
            "type": "receipt",
            "title": "Sandbox project created and verified",
            "status": "passed",
            "summary": f"Created and verified {len(writes)} files inside the sandbox workspace.",
            "payload": {"project": project, "files": writes, "previewPath": f"{project}/index.html", "dateSaved": date_saved, "hostSandboxRoot": _host_sandbox_root(request)},
        }
    ]
    return _chat_result(
        store=store,
        session_id=session_id,
        user_message_id=user_message_id,
        content=content,
        cards=cards,
        action_type="sandbox_project_create",
        attachments=attachments,
    )


def _handle_escape_probe(payload: ChatRequest, request: Request, store: PostgresStore, session_id: str, user_message_id: str, attachments: list[AttachmentReference]) -> ResultEnvelope[ChatResponse] | None:
    lower = payload.message.lower()
    if "escape" not in lower and "outside-sandbox" not in lower:
        return None
    targets = ESCAPE_TARGET_RE.findall(payload.message)
    if not targets:
        return None
    manager = _workspace(request)
    results = []
    for target in targets:
        candidate = target.strip()
        try:
            manager.resolve_inside_root(candidate)
            results.append({"path": candidate, "status": "ALLOWED", "reason": "inside sandbox root"})
        except ValueError as exc:
            results.append({"path": candidate, "status": "BLOCKED", "reason": str(exc)})
    lines = ["Sandbox escape probe completed without writing files.", ""]
    lines.extend(f"{item['status']}: {item['path']} — {item['reason']}" for item in results)
    cards = [
        {
            "type": "receipt",
            "title": "Sandbox escape probe",
            "status": "passed",
            "summary": "Outside-sandbox write targets were inspected without mutation.",
            "payload": {"results": results, "mutated": False},
        }
    ]
    return _chat_result(
        store=store,
        session_id=session_id,
        user_message_id=user_message_id,
        content="\n".join(lines),
        cards=cards,
        action_type="sandbox_escape_probe",
        attachments=attachments,
    )


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

    deterministic_result = _handle_sandbox_project_command(payload, request, store, session_id, user_message_id, attachments)
    if deterministic_result:
        return deterministic_result
    deterministic_result = _handle_escape_probe(payload, request, store, session_id, user_message_id, attachments)
    if deterministic_result:
        return deterministic_result

    session = store.get_session(session_id)
    session_messages = session["messages"] if session else []
    kernel_response = _kernel(request).handle(
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
        ),
        receipts=[envelope_receipt, *kernel_response.extra_receipts],
    )
