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
    return XV8Kernel(context, ModelRouter(OllamaAdapter(settings.ollama_base_url), profiles), brain_manager=brain_manager, continuity_manager=continuity_manager)


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


# XOWUI-BRIDGE-FASTAPI-01
# Thin Open WebUI bridge. Open WebUI remains the brain.
@router.post("/xoduz/openwebui-chat")
async def xoduz_openwebui_chat(request: Request):
    import json
    import os
    import re
    import time
    import urllib.error
    import urllib.request
    from fastapi import HTTPException

    payload = await request.json()

    user_message = str(
        payload.get("message")
        or payload.get("content")
        or payload.get("text")
        or payload.get("prompt")
        or ""
    ).strip()

    if not user_message and isinstance(payload.get("messages"), list):
        for item in reversed(payload.get("messages", [])):
            if isinstance(item, dict) and item.get("role") == "user":
                user_message = str(item.get("content", "")).strip()
                break

    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    base_url = os.getenv("OPENWEBUI_BASE_URL", "http://host.docker.internal:3000").rstrip("/")
    api_key = os.getenv("OPENWEBUI_API_KEY", "").strip()
    model = os.getenv("OPENWEBUI_MODEL", "qwen3:14b").strip()

    if not api_key:
        raise HTTPException(status_code=500, detail="OPENWEBUI_API_KEY is not configured")

    system_prompt = """You are Xoduz, Otis Duncan's private local-first AI assistant.

Name rule:
Your name is written as Xoduz. Always write it as Xoduz in visible chat text.
The pronunciation of Xoduz is like Exodus when spoken aloud.
Do not replace the written name with Exodus in visible text.
Do not say or write Zodus, Zodas, X-O-Duz, or X-O-Dus.
Do not spell the name unless the user specifically asks how it is spelled.

Answer directly, practically, and honestly. Work in tiny verified slices. Do not pretend to have live access to files, repos, Docker, tools, logs, memory, or system state unless that access was actually provided. When evidence is missing, say what is unknown and what should be checked next.

Coding/UI rule:
When you provide code, use fenced code blocks with the correct language label such as powershell, js, jsx, ts, tsx, python, json, yaml, html, or css. Do not claim the code ran unless actual tool output was provided.
If you provide a fenced code block, do not explain every line unless asked. X8 will place the code in an IDE card.
""".strip()

    body = {
        "model": model,
        "temperature": payload.get("temperature", 0.25),
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    req = urllib.request.Request(
        f"{base_url}/api/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail)
        except Exception:
            pass

        raise HTTPException(
            status_code=error.code,
            detail={
                "error": "Open WebUI request failed",
                "details": detail,
            },
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Open WebUI bridge failed",
                "details": str(error),
            },
        )

    raw_content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    now_ms = int(time.time() * 1000)
    session_id = str(payload.get("session_id") or payload.get("sessionId") or f"xowui_session_{now_ms}")
    message_id = f"xowui_msg_{now_ms}"
    receipt_id = f"xowui_receipt_{now_ms}"

    language_aliases = {
        "ps1": "powershell",
        "pwsh": "powershell",
        "shell": "bash",
        "sh": "bash",
        "javascript": "js",
        "typescript": "ts",
        "react": "jsx",
        "tsx": "tsx",
        "jsx": "jsx",
        "py": "python",
        "yml": "yaml",
    }

    extension_by_language = {
        "powershell": "ps1",
        "bash": "sh",
        "js": "js",
        "jsx": "jsx",
        "ts": "ts",
        "tsx": "tsx",
        "python": "py",
        "json": "json",
        "yaml": "yml",
        "html": "html",
        "css": "css",
        "markdown": "md",
    }

    def normalize_language(value: str) -> str:
        raw_language = re.sub(r"[^A-Za-z0-9_+.-]", "", (value or "").strip().lower())
        return language_aliases.get(raw_language, raw_language or "text")

    def title_for_language(language: str) -> str:
        labels = {
            "powershell": "PowerShell",
            "bash": "Shell",
            "js": "JavaScript",
            "jsx": "React JSX",
            "ts": "TypeScript",
            "tsx": "React TSX",
            "python": "Python",
            "json": "JSON",
            "yaml": "YAML",
            "html": "HTML",
            "css": "CSS",
            "markdown": "Markdown",
            "text": "Text",
        }
        return labels.get(language, language.upper())

    code_cards = []
    for index, match in enumerate(re.finditer(r"```([^\n`]*)\n([\s\S]*?)```", raw_content), start=1):
        language = normalize_language(match.group(1))
        code = match.group(2).strip("\n")
        if not code.strip():
            continue
        extension = extension_by_language.get(language, "txt")
        path = f"generated/openwebui-code-{index}.{extension}"
        code_cards.append(
            {
                "id": f"{message_id}_code_{index}",
                "type": "editor",
                "title": f"Code artifact: {title_for_language(language)}",
                "status": "draft",
                "summary": "Detected from an Open WebUI fenced code block. Not saved or executed.",
                "collapsed": False,
                "payload": {
                    "path": path,
                    "content": code,
                    "language": language,
                    "raw_content": raw_content,
                    "source": "open-webui-code-fence",
                    "execution_status": "not_run",
                    "write_status": "not_written",
                    "safety": "copy/edit only; execution requires separate approval",
                },
            }
        )

    visible_text = raw_content
    if code_cards:
        visible_text = "I placed the results in the chat. Does it need any revisions?"

    # Visible text stays Xoduz. Speech/TTS text gets pronunciation alias.
    speech_text = (
        visible_text
        .replace("Xoduz", "Exodus")
        .replace("XODUZ", "Exodus")
        .replace("xoduz", "Exodus")
    )

    assistant_message = {
        "message_id": message_id,
        "id": message_id,
        "role": "assistant",
        "content": visible_text,
        "text": visible_text,
        "speech_text": speech_text,
        "speechText": speech_text,
        "tts_text": speech_text,
        "ttsText": speech_text,
        "audio_text": speech_text,
        "audioText": speech_text,
        "type": "message",
        "cards": code_cards,
        "attachments": [],
        "sources": [],
        "source_pins": [],
        "sourcePins": [],
        "actions": [],
        "next_actions": [],
        "nextActions": [],
        "artifacts": [],
        "events": [],
        "warnings": [],
        "errors": [],
        "source": "open-webui",
        "model": model,
    }

    receipt = {
        "receipt_id": receipt_id,
        "action_type": "openwebui_chat",
        "status": "passed",
        "model": model,
        "source": "open-webui",
        "limitations": [],
        "warnings": [],
        "errors": [],
    }

    return {
        "ok": True,
        "success": True,
        "status": "passed",
        "message": "ok",
        "content": visible_text,
        "text": visible_text,
        "speech_text": speech_text,
        "speechText": speech_text,
        "tts_text": speech_text,
        "ttsText": speech_text,
        "audio_text": speech_text,
        "audioText": speech_text,
        "source": "open-webui",
        "model": model,
        "cards": code_cards,
        "attachments": [],
        "sources": [],
        "source_pins": [],
        "sourcePins": [],
        "actions": [],
        "next_actions": [],
        "nextActions": [],
        "artifacts": [],
        "events": [],
        "warnings": [],
        "errors": [],
        "receipts": [receipt],
        "assistant_message": assistant_message,
        "assistantMessage": assistant_message,
        "messages": [assistant_message],
        "validation": {
            "status": "unchecked",
            "warnings": [],
        },
        "data": {
            "session_id": session_id,
            "message_id": message_id,
            "assistant_message": assistant_message,
            "assistantMessage": assistant_message,
            "messages": [assistant_message],
            "receipt": receipt,
            "receipts": [receipt],
            "attachments": [],
            "cards": code_cards,
            "sources": [],
            "source_pins": [],
            "sourcePins": [],
            "actions": [],
            "next_actions": [],
            "nextActions": [],
            "artifacts": [],
            "events": [],
            "warnings": [],
            "errors": [],
            "content": visible_text,
            "text": visible_text,
            "message": visible_text,
            "speech_text": speech_text,
            "speechText": speech_text,
            "tts_text": speech_text,
            "ttsText": speech_text,
            "audio_text": speech_text,
            "audioText": speech_text,
            "source": "open-webui",
            "model": model,
            "validation": {
                "status": "unchecked",
                "warnings": [],
            },
        },
    }
