from datetime import datetime, timezone

from x8.contracts.chat import ModelStatus
from x8.kernel.contracts import ModelSelection
from x8.managers.model_manager import BLOCKED_MODELS, OllamaAdapter, normalize_model


class ModelProfileManager:
    def __init__(self, default_chat: str, fallback_chat: str, code: str = "", fast: str = "", embedding: str = "", reasoning: str = "", ollama_mode: str = "host_ollama_bridge", ollama_base_url: str = "") -> None:
        self.default_chat, default_blocked = normalize_model(default_chat, "qwen3:8b")
        self.fallback_chat, fallback_blocked = normalize_model(fallback_chat, "qwen3:1.7b")
        code_fallback = self.default_chat or "qwen3:8b"
        self.code, code_blocked = normalize_model(code, code_fallback)
        self.fast, fast_blocked = normalize_model(fast, "qwen3:1.7b")
        self.embedding, embedding_blocked = normalize_model(embedding, "nomic-embed-text:latest")
        self.reasoning, reasoning_blocked = normalize_model(reasoning, "qwen3:14b")
        self.ollama_mode = ollama_mode
        self.ollama_base_url = ollama_base_url
        self.configured_blocked_models = [model for model, blocked in ((default_chat, default_blocked), (fallback_chat, fallback_blocked), (code, code_blocked), (fast, fast_blocked), (reasoning, reasoning_blocked), (embedding, embedding_blocked)) if blocked]


class ModelRouter:
    def __init__(self, adapter: OllamaAdapter, profiles: ModelProfileManager) -> None:
        self.adapter = adapter
        self.profiles = profiles

    def select(self, lane: str) -> tuple[ModelStatus, ModelSelection]:
        reachable, models, reason = self.adapter.models()
        selectable_models = [model for model in models if model not in BLOCKED_MODELS]
        preferred = self._preferred_model(lane)
        selected = preferred if preferred and preferred in selectable_models else ""
        fallback_used = False
        if not selected and self.profiles.fallback_chat and self.profiles.fallback_chat in selectable_models:
            selected = self.profiles.fallback_chat
            fallback_used = True
        if not selected and selectable_models and not preferred:
            selected = selectable_models[0]
        ready = reachable and bool(selected)
        failure = "" if ready else (reason or "No configured chat model is available.")
        configured = [self.profiles.default_chat, self.profiles.reasoning, self.profiles.fallback_chat, self.profiles.code, self.profiles.embedding]
        missing = [model for model in configured if model and model not in selectable_models]
        status = ModelStatus(
            ollama_mode=self.profiles.ollama_mode,
            ollama_base_url=getattr(self.adapter, "base_url", self.profiles.ollama_base_url),
            ollama_reachable=reachable,
            available_models=models,
            blocked_models=sorted(BLOCKED_MODELS),
            installed_but_blocked=[model for model in models if model in BLOCKED_MODELS],
            blocked_model_configured=self.profiles.configured_blocked_models,
            default_chat_model=self.profiles.default_chat,
            reasoning_model=self.profiles.reasoning,
            fallback_chat_model=self.profiles.fallback_chat,
            code_model=self.profiles.code,
            embedding_model=self.profiles.embedding,
            selected_model=selected,
            model_ready=ready,
            missing_models=missing,
            last_checked_at=datetime.now(timezone.utc),
            failure_reason=failure,
            fallback_used=fallback_used,
            timed_out=False,
            timeout_seconds=0.0,
            reason_if_unavailable=failure,
            health_prompt_succeeded=ready,
            embedding_ready=bool(self.profiles.embedding and self.profiles.embedding in selectable_models),
        )
        selection = ModelSelection(selected_model=selected, fallback_used=fallback_used, model_ready=ready, reason_if_unavailable=failure, available_models=models)
        return status, selection

    def _preferred_model(self, lane: str) -> str:
        if lane in {"code_help", "repo_inspection"} and self.profiles.code:
            return self.profiles.code
        if lane in {"reasoning", "deep_planning"} and self.profiles.reasoning:
            return self.profiles.reasoning
        if lane == "fast" and self.profiles.fast:
            return self.profiles.fast
        return self.profiles.default_chat

    def generate(self, selection: ModelSelection, prompt: str) -> tuple[bool, str, str]:
        if not selection.model_ready:
            return False, "", selection.reason_if_unavailable
        ok, content, reason = self.adapter.generate(selection.selected_model, prompt)
        generation = getattr(self.adapter, "last_generation_result", None)
        if generation is not None:
            selection.selected_model = getattr(generation, "model", selection.selected_model) or selection.selected_model
            selection.fallback_used = bool(getattr(generation, "fallback_used", selection.fallback_used))
            selection.timed_out = bool(getattr(generation, "timed_out", selection.timed_out))
            selection.timeout_seconds = float(getattr(generation, "timeout_seconds", selection.timeout_seconds) or 0.0)
            selection.reason_if_unavailable = getattr(generation, "failure_reason", reason) or reason
        return ok, content, reason
