from __future__ import annotations

from x8.brain.continuity_manager import BrainContinuityManager
from x8.brain.embedding_client import OllamaEmbeddingClient
from x8.brain.memory_manager import BrainMemoryManager
from x8.kernel.brain_context import BrainContextAssembler
from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.kernel import XV8Kernel
from x8.kernel.model_router import ModelProfileManager, ModelRouter
from x8.kernel.prompt_builder import KernelPromptBuilder
from x8.managers.brain_bridge_adapter import env_first
from x8.managers.brain_bridge_factory import build_adapter, selected_chat_model
from x8.managers.memory_manager import MemoryManager

MODEL_OWNED_PROVIDERS = {"openwebui", "owui", "brainbridge"}
GREETING_TEXT = {"hi", "hi xv8", "hi xoduz", "hello", "hello xv8", "hello xoduz", "hey", "hey xv8", "hey xoduz", "good morning", "good afternoon", "good evening"}
IDENTITY_TEXT = {"who are you", "who are you?"}


def provider() -> str:
    return env_first("X8_CHAT_PROVIDER", "CHAT_PROVIDER", default="openwebui").strip().lower().replace("-", "").replace("_", "")


class OpenWebUIBridgeKernel(XV8Kernel):
    """Kernel variant for model-owned Open Web UI chat.

    Normal greeting and identity turns must not be treated as proof that the
    model works. If the bridge is ready, the prompt goes to the model. If the
    bridge is not ready, the answer is an explicit unavailable status.
    """

    def _deterministic_response(self, request, lane: str, bundle, selection=None):
        lower = request.user_message.lower().strip()
        if lower in GREETING_TEXT or lower in IDENTITY_TEXT or "what is your name" in lower:
            if getattr(selection, "model_ready", False):
                return None
            reason = getattr(selection, "reason_if_unavailable", "") or "Open Web UI brain bridge is not ready."
            return (
                "Kernel identity is available, but model-owned chat must use the Open Web UI brain bridge. The bridge is not ready: " + reason,
                "unavailable",
                [reason],
            )
        return super()._deterministic_response(request, lane, bundle, selection)

    def _x8_memory_capture_allowed(self, lane: str) -> bool:
        return False


def build_bridge_kernel(request) -> XV8Kernel:
    settings = request.app.state.settings
    limits = {
        "context_max_messages": settings.context_max_messages,
        "context_max_attachment_chars": settings.context_max_attachment_chars,
        "context_max_memory_items": settings.context_max_memory_items,
        "context_max_knowledge_items": settings.context_max_knowledge_items,
    }
    brain = BrainContextAssembler(
        settings.knowledge_root,
        limits,
        MemoryManager(settings.memory_storage_path) if settings.memory_enabled and provider() not in MODEL_OWNED_PROVIDERS else None,
    )
    context = KernelContextAssembler(brain, KernelPromptBuilder())
    adapter = build_adapter(settings)
    profiles = ModelProfileManager(
        selected_chat_model(settings),
        settings.fallback_chat_model,
        settings.code_model,
        settings.fast_model,
        settings.embedding_model,
        settings.reasoning_model,
        f"{provider()}:{settings.ollama_mode}",
        getattr(adapter, "base_url", settings.ollama_base_url),
    )
    brain_manager = BrainMemoryManager(
        settings.database_url,
        memory_enabled=False,
        global_enabled=False,
        project_enabled=False,
        session_enabled=False,
        auto_capture_enabled=False,
        auto_capture_min_confidence=settings.memory_auto_capture_min_confidence,
        auto_capture_max_per_turn=settings.memory_auto_capture_max_per_turn,
        auto_capture_receipts_enabled=settings.memory_auto_capture_receipts_enabled,
        semantic_retrieval_enabled=False,
        embedding_enabled=False,
        embedding_client=OllamaEmbeddingClient(settings.ollama_base_url, settings.embedding_model),
        embedding_model=settings.embedding_model,
        retrieval_max_results=settings.memory_retrieval_max_results,
        retrieval_min_score=settings.memory_retrieval_min_score,
    )
    continuity_manager = BrainContinuityManager(settings.database_url)
    return OpenWebUIBridgeKernel(context, ModelRouter(adapter, profiles), brain_manager=brain_manager, continuity_manager=continuity_manager)


def apply_runtime_patch() -> None:
    return None
