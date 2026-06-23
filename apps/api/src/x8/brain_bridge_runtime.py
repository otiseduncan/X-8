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


def provider() -> str:
    return env_first("X8_CHAT_PROVIDER", "CHAT_PROVIDER", default="openwebui").strip().lower().replace("-", "").replace("_", "")


def build_bridge_kernel(request) -> XV8Kernel:
    settings = request.app.state.settings
    limits = {
        "context_max_messages": settings.context_max_messages,
        "context_max_attachment_chars": settings.context_max_attachment_chars,
        "context_max_memory_items": settings.context_max_memory_items,
        "context_max_knowledge_items": settings.context_max_knowledge_items,
    }

    # OpenWebUI owns conversational memory. X8 may still assemble deterministic
    # operator context, but local X8 conversational memory is disabled unless an
    # explicit operator asks for it outside the model-owned lane.
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
    return XV8Kernel(context, ModelRouter(adapter, profiles), brain_manager=brain_manager, continuity_manager=continuity_manager)


def apply_runtime_patch() -> None:
    """Deprecated compatibility shim.

    The chat route now calls build_bridge_kernel directly. This function remains
    as a no-op so older imports do not break, but it must not monkey-patch core
    chat routing.
    """
    return None
