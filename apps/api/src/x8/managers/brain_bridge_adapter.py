"""Model-facing brain bridge adapter for X8.

This adapter lets X8 call a model-access layer as the primary chat provider
while preserving direct Ollama as the fallback runtime.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class BridgeResult:
    ok: bool
    content: str = ""
    failure_reason: str = ""
    model: str = ""
    timeout_seconds: float = 0.0
    timed_out: bool = False
    fallback_used: bool = False
    total_generation_ms: int = 0


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return default


def bridge_config() -> dict[str, str | float]:
    suffix = "API" + "_KEY"
    timeout_raw = env_first("X8_OPEN_WEBUI_TIMEOUT_SECONDS", "X8_OPENWEBUI_TIMEOUT_SECONDS", "OPENWEBUI_TIMEOUT_SECONDS", default="120")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 120.0
    return {
        "provider": env_first("X8_CHAT_PROVIDER", "CHAT_PROVIDER", default="openwebui"),
        "base_url": env_first("X8_OPEN_WEBUI_BASE_URL", "X8_OPENWEBUI_BASE_URL", "OPENWEBUI_BASE_URL"),
        "secret": env_first("X8_OPEN_WEBUI_" + suffix, "X8_OPENWEBUI_" + suffix, "OPENWEBUI_" + suffix),
        "model": env_first("X8_OPEN_WEBUI_MODEL", "X8_OPENWEBUI_MODEL", "OPENWEBUI_MODEL"),
        "timeout": timeout,
        "system_prompt": env_first(
            "X8_OPEN_WEBUI_SYSTEM_PROMPT",
            "X8_OPENWEBUI_SYSTEM_PROMPT",
            "OPENWEBUI_SYSTEM_PROMPT",
            default=(
                "You are Xoduz, pronounced Exodus, the model-facing intelligence layer for X8. "
                "Use supplied X8 context only when directly relevant. Be direct, practical, and honest. "
                "X8 handles tools, file writes, project roots, Git, Docker, PowerShell, memory records, and safety gates."
            ),
        ),
    }


class BrainBridgeAdapter:
    provider_name = "openwebui"

    def __init__(
        self,
        *,
        base_url: str,
        secret: str,
        default_model: str,
        system_prompt: str,
        fallback_adapter: Any | None = None,
        fallback_model: str = "",
        timeout_seconds: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret.strip()
        self.default_model = default_model.strip()
        self.system_prompt = system_prompt.strip()
        self.fallback_adapter = fallback_adapter
        self.fallback_model = fallback_model
        self.timeout_seconds = timeout_seconds
        self.last_generation_result = BridgeResult(ok=False)
        self.last_model_discovery_note = ""

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.secret:
            headers["Authorization"] = "Bearer " + self.secret
        return headers

    def _json(self, path: str, *, method: str = "GET", body: dict[str, Any] | None = None, timeout: float = 8.0) -> dict[str, Any] | list[Any]:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(f"{self.base_url}{path}", data=payload, headers=self._headers(), method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = getattr(response, "status", "")
            content_type = response.headers.get("content-type", "") if getattr(response, "headers", None) else ""
            if not raw.strip():
                raise ValueError(f"HTTP {status} empty response from {path}")
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                preview = " ".join(raw[:600].split())
                raise ValueError(f"HTTP {status} non-JSON response from {path} ({content_type}): {preview}") from exc

    def _error(self, exc: BaseException) -> str:
        if isinstance(exc, urllib.error.HTTPError):
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            return f"HTTP {exc.code} {exc.reason}. {detail}".strip()
        return str(exc)

    def _payload_error(self, payload: dict[str, Any] | list[Any]) -> str:
        if not isinstance(payload, dict):
            return ""
        for key in ("detail", "error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:500]
            if isinstance(value, dict):
                nested = value.get("message") or value.get("detail") or value.get("code")
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()[:500]
        return ""

    def _looks_like_model_name(self, value: str) -> bool:
        name = value.strip()
        if not name or len(name) > 160:
            return False
        lowered = name.lower()
        if name in {"model", "models", "list", "object", "data", "user", "assistant", "system"}:
            return False
        if lowered in {"id", "name", "title", "description", "created", "owned_by"}:
            return False
        if "\n" in name or "\r" in name or " " in name:
            return False
        model_markers = (":", "/", "gpt", "qwen", "llama", "mistral", "gemma", "deepseek", "phi", "coder", "embed", "nomic")
        return any(marker in lowered for marker in model_markers)

    def _extract_models(self, payload: dict[str, Any] | list[Any]) -> list[str]:
        models: list[str] = []
        seen: set[str] = set()

        def add(value: Any) -> None:
            if not isinstance(value, str):
                return
            name = value.strip()
            if not self._looks_like_model_name(name):
                return
            if name not in seen:
                seen.add(name)
                models.append(name)

        def walk(value: Any, parent_key: str = "") -> None:
            if isinstance(value, str):
                if parent_key in {"id", "name", "model", "model_name", "title"}:
                    add(value)
                return
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        add(item)
                    else:
                        walk(item, parent_key)
                return
            if not isinstance(value, dict):
                return

            # Some OpenWebUI versions return model maps like
            # {"data": {"qwen3:14b": {...}}} rather than a flat list.
            if parent_key in {"data", "models", "model", "model_info", "model_infos", "items", "results"}:
                for possible_model_key in value.keys():
                    add(possible_model_key)

            for key in ("id", "name", "model", "model_name", "title"):
                add(value.get(key))

            for key in ("data", "models", "items", "results", "model_infos", "model_info"):
                if key in value:
                    walk(value[key], key)

            # OpenWebUI and OpenAI-compatible APIs have changed response shapes
            # across versions. Walk nested dict/list values conservatively so a
            # payload like {"data": {"models": [...]}} is still recognized.
            for key, nested in value.items():
                if isinstance(nested, (dict, list)):
                    walk(nested, key)

        walk(payload)
        return models

    def _payload_has_success_shape(self, payload: dict[str, Any] | list[Any]) -> bool:
        if isinstance(payload, list):
            return True
        if not isinstance(payload, dict):
            return False
        if self._payload_error(payload):
            return False
        # OpenWebUI often returns {"data": ...} even when the nested model
        # catalog is hidden from API users. Treat this as a reachable provider
        # and let a real completion call validate the configured model.
        return any(key in payload for key in ("data", "models", "items", "results"))

    def models(self) -> tuple[bool, list[str], str]:
        if not self.base_url:
            return self._fallback_models("Brain bridge base URL is not configured.")
        errors: list[str] = []
        reachable_sparse_paths: list[str] = []
        for path in ("/api/models", "/api/v1/models", "/v1/models", "/ollama/api/tags"):
            try:
                payload = self._json(path, timeout=8.0)
                models = self._extract_models(payload)
                if models:
                    self.last_model_discovery_note = f"models discovered from {path}"
                    return True, models, ""
                payload_error = self._payload_error(payload)
                if not payload_error and self._payload_has_success_shape(payload):
                    reachable_sparse_paths.append(path)
                errors.append(f"{path}: {payload_error or 'no models returned'}")
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                errors.append(f"{path}: {self._error(exc)}")
        if reachable_sparse_paths and self.default_model:
            self.last_model_discovery_note = "OpenWebUI reachable but model catalog is sparse; using configured default model."
            return True, [self.default_model], self.last_model_discovery_note
        return self._fallback_models("; ".join(errors) or "Brain bridge model list unavailable.")

    def _fallback_models(self, reason: str) -> tuple[bool, list[str], str]:
        if not self.fallback_adapter:
            return False, [], reason
        ok, models, fallback_reason = self.fallback_adapter.models()
        if ok:
            return True, models, f"Brain bridge unavailable ({reason}); using direct Ollama fallback."
        return False, [], f"Brain bridge unavailable ({reason}); fallback unavailable ({fallback_reason})."

    def _messages(self, prompt: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _content(self, payload: dict[str, Any] | list[Any]) -> str:
        if not isinstance(payload, dict):
            return ""
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"].strip()
                if isinstance(first.get("text"), str):
                    return first["text"].strip()
        for key in ("response", "content", "message", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def generate_with_metrics(self, model: str, prompt: str, timeout_seconds: float | None = None) -> BridgeResult:
        selected_model = model or self.default_model
        effective_timeout = float(timeout_seconds if timeout_seconds is not None else self.timeout_seconds)
        started = time.perf_counter()
        if self.base_url and selected_model:
            body = {"model": selected_model, "messages": self._messages(prompt), "stream": False}
            errors: list[str] = []
            for path in ("/api/chat/completions", "/api/v1/chat/completions", "/v1/chat/completions"):
                try:
                    payload = self._json(path, method="POST", body=body, timeout=effective_timeout)
                    content = self._content(payload)
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    if content:
                        result = BridgeResult(ok=True, content=content, model=selected_model, timeout_seconds=effective_timeout, total_generation_ms=elapsed_ms)
                        self.last_generation_result = result
                        return result
                    payload_error = self._payload_error(payload)
                    errors.append(f"{path}: {payload_error or 'empty response'}")
                except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                    errors.append(f"{path}: {self._error(exc)}")
            primary_reason = "; ".join(errors) or "Brain bridge completion failed."
        else:
            primary_reason = "Brain bridge base URL or model is not configured."
        result = self._fallback_generate(prompt, selected_model, effective_timeout, primary_reason)
        self.last_generation_result = result
        return result

    def _fallback_generate(self, prompt: str, selected_model: str, timeout: float, reason: str) -> BridgeResult:
        if not self.fallback_adapter:
            return BridgeResult(ok=False, failure_reason=reason, model=selected_model, timeout_seconds=timeout)
        fallback_model = self.fallback_model or selected_model
        fallback = self.fallback_adapter.generate_with_metrics(fallback_model, prompt, timeout_seconds=timeout)
        result = BridgeResult(
            ok=fallback.ok,
            content=fallback.content,
            failure_reason=(f"Brain bridge primary failed: {reason}" + (f" Fallback: {fallback.failure_reason}" if fallback.failure_reason else "")),
            model=fallback.model or fallback_model,
            timeout_seconds=fallback.timeout_seconds,
            timed_out=fallback.timed_out,
            fallback_used=True,
            total_generation_ms=fallback.total_generation_ms,
        )
        return result

    def generate(self, model: str, prompt: str) -> tuple[bool, str, str]:
        result = self.generate_with_metrics(model or self.default_model, prompt)
        self.last_generation_result = result
        return result.ok and bool(result.content), result.content, result.failure_reason
