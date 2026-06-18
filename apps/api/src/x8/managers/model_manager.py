import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from x8.contracts.chat import ModelStatus

BLOCKED_MODELS = {"qwen3-coder:30b"}


def normalize_model(model: str, fallback: str = "") -> tuple[str, bool]:
    if model in BLOCKED_MODELS:
        return fallback, True
    return model, False


class OllamaAdapter:
    def __init__(self, base_url: str, timeout_seconds: float = 3.0, generate_timeout_seconds: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.generate_timeout_seconds = generate_timeout_seconds

    def models(self) -> tuple[bool, list[str], str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return True, [item.get("name", "") for item in payload.get("models", []) if item.get("name")], ""
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return False, [], str(exc)

    def generate(self, model: str, prompt: str) -> tuple[bool, str, str]:
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        try:
            request = urllib.request.Request(f"{self.base_url}/api/generate", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=self.generate_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return True, str(payload.get("response", "")).strip(), ""
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return False, "", str(exc)

    def embed(self, model: str, text: str) -> tuple[bool, list[float], str]:
        body = json.dumps({"model": model, "prompt": text}).encode("utf-8")
        try:
            request = urllib.request.Request(f"{self.base_url}/api/embeddings", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=self.generate_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            embedding = payload.get("embedding", [])
            if not isinstance(embedding, list):
                return False, [], "Ollama embedding response did not include an embedding list."
            return True, [float(value) for value in embedding], ""
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
            return False, [], str(exc)


class ModelReadinessManager:
    def __init__(
        self,
        adapter: OllamaAdapter,
        default_model: str,
        fallback_model: str,
        *,
        ollama_mode: str = "host_ollama_bridge",
        reasoning_model: str = "",
        code_model: str = "",
        embedding_model: str = "",
        health_prompt: str = "Reply with XV8_READY only.",
        embedding_required_for_memory: bool = True,
    ) -> None:
        self.adapter = adapter
        self.default_model, default_blocked = normalize_model(default_model, "qwen3:8b")
        self.fallback_model, fallback_blocked = normalize_model(fallback_model, "qwen3:1.7b")
        self.ollama_mode = ollama_mode
        self.reasoning_model, reasoning_blocked = normalize_model(reasoning_model, "qwen3:14b")
        code_fallback = self.default_model or "qwen3:8b"
        self.code_model, code_blocked = normalize_model(code_model, code_fallback)
        self.embedding_model, embedding_blocked = normalize_model(embedding_model, "nomic-embed-text:latest")
        self.configured_blocked_models = [model for model, blocked in ((default_model, default_blocked), (reasoning_model, reasoning_blocked), (fallback_model, fallback_blocked), (code_model, code_blocked), (embedding_model, embedding_blocked)) if blocked]
        self.health_prompt = health_prompt
        self.embedding_required_for_memory = embedding_required_for_memory

    def status(self, *, probe: bool = True) -> ModelStatus:
        reachable, models, reason = self.adapter.models()
        selectable_models = [model for model in models if model not in BLOCKED_MODELS]
        selected = ""
        fallback_used = False
        if self.default_model and self.default_model in selectable_models:
            selected = self.default_model
        elif self.fallback_model and self.fallback_model in selectable_models:
            selected = self.fallback_model
            fallback_used = True
        elif selectable_models and not self.default_model:
            selected = selectable_models[0]
        configured = [self.default_model, self.reasoning_model, self.fallback_model, self.code_model, self.embedding_model]
        missing = [model for model in configured if model and model not in selectable_models]
        health_ok = False
        health_reason = ""
        if reachable and selected and probe:
            health_ok, content, health_reason = self.adapter.generate(selected, self.health_prompt)
            health_ok = health_ok and "XV8_READY" in content
            if not health_ok and not health_reason:
                health_reason = "Model health prompt did not return XV8_READY."
        embedding_ok = bool(self.embedding_model) and self.embedding_model in selectable_models
        ready = reachable and bool(selected) and (health_ok if probe else True)
        failure = "" if ready else (health_reason or reason or "No configured chat model is available.")
        if not ready and self.ollama_mode == "docker_ollama" and missing:
            pulls = "\n".join(f"docker compose exec x8-ollama ollama pull {model}" for model in missing)
            failure = f"{failure}\nMissing Docker Ollama models can be installed with:\n{pulls}"
        return ModelStatus(
            ollama_mode=self.ollama_mode,
            ollama_base_url=self.adapter.base_url,
            ollama_reachable=reachable,
            available_models=models,
            blocked_models=sorted(BLOCKED_MODELS),
            installed_but_blocked=[model for model in models if model in BLOCKED_MODELS],
            blocked_model_configured=self.configured_blocked_models,
            default_chat_model=self.default_model,
            reasoning_model=self.reasoning_model,
            fallback_chat_model=self.fallback_model,
            code_model=self.code_model,
            embedding_model=self.embedding_model,
            selected_model=selected,
            model_ready=ready,
            missing_models=missing,
            last_checked_at=datetime.now(timezone.utc),
            failure_reason=failure,
            fallback_used=fallback_used,
            reason_if_unavailable=failure,
            health_prompt_succeeded=health_ok,
            embedding_ready=embedding_ok,
            memory_ready=ready and (embedding_ok or not self.embedding_required_for_memory),
        )


class ModelProvider:
    def __init__(self, adapter: OllamaAdapter, readiness: ModelReadinessManager) -> None:
        self.adapter = adapter
        self.readiness = readiness

    def respond(self, prompt: str) -> tuple[ModelStatus, str]:
        status = self.readiness.status()
        if not status.model_ready:
            return status, "The assistant model is unavailable right now.\nNo model response was generated.\nCheck Settings > Model + Runtime."
        ok, content, reason = self.adapter.generate(status.selected_model, prompt)
        if ok and content:
            return status, content
        status.model_ready = False
        status.failure_reason = reason or "Model returned an empty response."
        return status, "The assistant model is unavailable right now.\nNo model response was generated.\nCheck Settings > Model + Runtime."
