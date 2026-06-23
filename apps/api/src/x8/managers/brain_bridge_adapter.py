"""OpenWebUI-owned model bridge for X8.

This module is intentionally strict: when X8 is configured for the
OpenWebUI brain path, X8 must not silently fall back to a direct Ollama
conversation and pretend the OpenWebUI brain worked. Direct Ollama remains a
separate provider path, not a hidden rescue path for model-owned chat.
"""

from __future__ import annotations

import json
import os
import re
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


def split_env_list(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[;,]", value) if item.strip()]


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
        "model_aliases": env_first("X8_OPEN_WEBUI_MODEL_ALIASES", "X8_OPENWEBUI_MODEL_ALIASES", "OPENWEBUI_MODEL_ALIASES"),
        "timeout": timeout,
        "system_prompt": env_first(
            "X8_OPEN_WEBUI_SYSTEM_PROMPT",
            "X8_OPENWEBUI_SYSTEM_PROMPT",
            "OPENWEBUI_SYSTEM_PROMPT",
            default=(
                "You are Xoduz, pronounced Exodus, the OpenWebUI brain/model layer for X8. "
                "OpenWebUI owns conversational memory, persona, preferences, and natural recall. "
                "X8 owns deterministic operator state, approvals, receipts, sandbox writes, GitHub operations, and safety gates. "
                "Be direct, practical, and honest. Do not claim tool actions happened unless X8 receipts prove them."
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
        model_aliases: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret.strip()
        self.default_model = default_model.strip()
        self.model_aliases = split_env_list(model_aliases)
        self.system_prompt = system_prompt.strip()
        self.fallback_adapter = fallback_adapter
        self.fallback_model = fallback_model
        self.timeout_seconds = timeout_seconds
        self.last_generation_result = BridgeResult(ok=False)
        self.last_model_discovery_note = ""
        self.last_model_discovery_errors: list[str] = []

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
            if parent_key in {"data", "models", "model", "model_info", "model_infos", "items", "results"}:
                for possible_model_key in value.keys():
                    add(possible_model_key)
            for key in ("id", "name", "model", "model_name", "title"):
                add(value.get(key))
            for key in ("data", "models", "items", "results", "model_infos", "model_info"):
                if key in value:
                    walk(value[key], key)
            for key, nested in value.items():
                if isinstance(nested, (dict, list)):
                    walk(nested, key)

        walk(payload)
        return models

    def _payload_has_catalog_shape(self, payload: dict[str, Any] | list[Any]) -> bool:
        if isinstance(payload, list):
            return True
        return isinstance(payload, dict) and any(key in payload for key in ("data", "models", "items", "results"))

    def _candidate_models(self, selected_model: str) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()

        def add(value: str) -> None:
            name = (value or "").strip()
            if name and name not in seen:
                seen.add(name)
                candidates.append(name)

        add(selected_model)
        add(self.default_model)
        for alias in self.model_aliases:
            add(alias)
        return candidates

    def models(self) -> tuple[bool, list[str], str]:
        if not self.base_url:
            return False, [], "OpenWebUI bridge base URL is not configured."
        if not self.secret:
            return False, [], "OpenWebUI API key is not configured."

        errors: list[str] = []
        reachable = False
        authenticated = False
        saw_catalog_shape = False
        for path in ("/api/models", "/api/v1/models", "/ollama/api/tags"):
            try:
                payload = self._json(path, timeout=8.0)
                reachable = True
                authenticated = True
                models = self._extract_models(payload)
                if models:
                    self.last_model_discovery_note = f"OpenWebUI models discovered from {path}."
                    self.last_model_discovery_errors = []
                    return True, models, ""
                if self._payload_has_catalog_shape(payload):
                    saw_catalog_shape = True
                payload_error = self._payload_error(payload)
                errors.append(f"{path}: {payload_error or 'authenticated but no models returned'}")
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 403}:
                    reachable = True
                    errors.append(f"{path}: OpenWebUI authentication failed ({self._error(exc)})")
                else:
                    errors.append(f"{path}: {self._error(exc)}")
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                errors.append(f"{path}: {self._error(exc)}")

        self.last_model_discovery_errors = errors
        if reachable and not authenticated:
            return False, [], "; ".join(errors) or "OpenWebUI is reachable but rejected authentication."
        if authenticated and saw_catalog_shape:
            return False, [], "OpenWebUI is reachable and authenticated, but it exposes zero models. Connect OpenWebUI to the Ollama backend that has the models. " + "; ".join(errors)
        return False, [], "; ".join(errors) or "OpenWebUI model catalog unavailable."

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
        message_value = payload.get("message")
        if isinstance(message_value, dict):
            content = message_value.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        data_value = payload.get("data")
        if isinstance(data_value, dict):
            nested = self._content(data_value)
            if nested:
                return nested
        for key in ("response", "content", "message", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _completion_attempts(self, model: str, prompt: str) -> list[tuple[str, dict[str, Any]]]:
        messages = self._messages(prompt)
        openai_body = {"model": model, "messages": messages, "stream": False}
        ollama_chat_body = {"model": model, "messages": messages, "stream": False}
        ollama_generate_body: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if self.system_prompt:
            ollama_generate_body["system"] = self.system_prompt
        return [
            ("/api/chat/completions", openai_body),
            ("/api/v1/chat/completions", openai_body),
            ("/ollama/api/chat", ollama_chat_body),
            ("/ollama/api/generate", ollama_generate_body),
        ]

    def generate_with_metrics(self, model: str, prompt: str, timeout_seconds: float | None = None) -> BridgeResult:
        effective_timeout = float(timeout_seconds if timeout_seconds is not None else self.timeout_seconds)
        started = time.perf_counter()
        selected_model = (model or self.default_model).strip()
        reachable, available_models, reason = self.models()
        if not reachable:
            result = BridgeResult(ok=False, failure_reason=reason, model=selected_model, timeout_seconds=effective_timeout)
            self.last_generation_result = result
            return result
        if selected_model not in available_models:
            preview = ", ".join(available_models[:12]) or "none"
            result = BridgeResult(
                ok=False,
                failure_reason=f"Selected OpenWebUI model '{selected_model}' is not available. Available OpenWebUI models: {preview}.",
                model=selected_model,
                timeout_seconds=effective_timeout,
            )
            self.last_generation_result = result
            return result

        errors: list[str] = []
        for path, body in self._completion_attempts(selected_model, prompt):
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
        result = BridgeResult(
            ok=False,
            failure_reason="OpenWebUI completion failed for the selected model. " + "; ".join(errors),
            model=selected_model,
            timeout_seconds=effective_timeout,
            total_generation_ms=int((time.perf_counter() - started) * 1000),
        )
        self.last_generation_result = result
        return result

    def generate(self, model: str, prompt: str) -> tuple[bool, str, str]:
        result = self.generate_with_metrics(model or self.default_model, prompt)
        self.last_generation_result = result
        return result.ok and bool(result.content), result.content, result.failure_reason
