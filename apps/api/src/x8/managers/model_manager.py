import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from x8.contracts.chat import ModelStatus

BLOCKED_MODELS = {"qwen3-coder:30b"}


def normalize_model(model: str, fallback: str = "") -> tuple[str, bool]:
    if model in BLOCKED_MODELS:
        return fallback, True
    return model, False


@dataclass
class GenerateResult:
    ok: bool
    content: str = ""
    failure_reason: str = ""
    model: str = ""
    timeout_seconds: float = 0.0
    timed_out: bool = False
    fallback_used: bool = False
    total_generation_ms: int = 0


def _timed_out(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", "")
    text = f"{exc} {reason}".lower()
    return isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in text or "timeout" in text


class OllamaAdapter:
    def __init__(self, base_url: str, timeout_seconds: float = 3.0, generate_timeout_seconds: float = 120.0, fallback_model: str = "qwen3:1.7b", fallback_timeout_seconds: float = 45.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.generate_timeout_seconds = generate_timeout_seconds
        self.fallback_model = fallback_model
        self.fallback_timeout_seconds = fallback_timeout_seconds
        self.last_generation_result = GenerateResult(ok=False)

    def models(self) -> tuple[bool, list[str], str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return True, [item.get("name", "") for item in payload.get("models", []) if item.get("name")], ""
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return False, [], str(exc)

    def generate_with_metrics(self, model: str, prompt: str, timeout_seconds: float | None = None) -> GenerateResult:
        effective_timeout = float(timeout_seconds if timeout_seconds is not None else self.generate_timeout_seconds)
        started = time.perf_counter()
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        try:
            request = urllib.request.Request(f"{self.base_url}/api/generate", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=effective_timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return GenerateResult(
                ok=True,
                content=str(payload.get("response", "")).strip(),
                model=model,
                timeout_seconds=effective_timeout,
                total_generation_ms=elapsed_ms,
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            timed_out = _timed_out(exc)
            reason = f"Model request timed out after {effective_timeout:g}s." if timed_out else str(exc)
            return GenerateResult(
                ok=False,
                content="",
                failure_reason=reason,
                model=model,
                timeout_seconds=effective_timeout,
                timed_out=timed_out,
                total_generation_ms=elapsed_ms,
            )

    def generate(self, model: str, prompt: str) -> tuple[bool, str, str]:
        result = self.generate_with_metrics(model, prompt)
        self.last_generation_result = result
        if result.ok and result.content:
            return result.ok, result.content, result.failure_reason
        if result.timed_out and model == "qwen3:8b" and self.fallback_model:
            fallback = self.generate_with_metrics(self.fallback_model, prompt, timeout_seconds=self.fallback_timeout_seconds)
            fallback.timed_out = True
            fallback.fallback_used = True
            fallback.timeout_seconds = result.timeout_seconds
            fallback.total_generation_ms += result.total_generation_ms
            fallback.failure_reason = f"Primary model {model} timed out after {result.timeout_seconds:g}s. Fallback model {self.fallback_model} responded." if fallback.ok and fallback.content else f"Primary model {model} timed out after {result.timeout_seconds:g}s. Fallback model {self.fallback_model} failed."
            self.last_generation_result = fallback
            return fallback.ok, fallback.content, fallback.failure_reason
        return result.ok, result.content, result.failure_reason

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
        health_timeout_seconds: float = 20.0,
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
        self.health_timeout_seconds = health_timeout_seconds
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
        timed_out = False
        timeout_seconds = 0.0
        if reachable and selected and probe:
            if hasattr(self.adapter, "generate_with_metrics"):
                health_result = self.adapter.generate_with_metrics(selected, self.health_prompt, timeout_seconds=self.health_timeout_seconds)
            else:
                ok, content, health_reason = self.adapter.generate(selected, self.health_prompt)
                health_result = GenerateResult(ok=ok, content=content, failure_reason=health_reason, model=selected, timeout_seconds=self.health_timeout_seconds)
            health_ok = health_result.ok and "XV8_READY" in health_result.content
            health_reason = health_result.failure_reason
            timed_out = health_result.timed_out
            timeout_seconds = health_result.timeout_seconds
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
            timed_out=timed_out,
            timeout_seconds=timeout_seconds,
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
