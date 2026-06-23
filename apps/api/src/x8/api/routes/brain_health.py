from __future__ import annotations

import urllib.error
from typing import Any

from fastapi import APIRouter, Request

from x8.managers.brain_bridge_factory import build_adapter, provider_name, selected_chat_model

router = APIRouter(prefix="/api", tags=["brain-health"])

OPENWEBUI_PROVIDER_NAMES = {"openwebui", "owui", "brainbridge"}


def _shape(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"type": "list", "length": len(payload)}
    if isinstance(payload, dict):
        shaped: dict[str, Any] = {"type": "dict", "keys": list(payload.keys())[:20]}
        for key in ("data", "models", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                shaped[f"{key}_length"] = len(value)
            elif isinstance(value, dict):
                shaped[f"{key}_keys"] = list(value.keys())[:20]
        return shaped
    return {"type": type(payload).__name__}


def _error(adapter: Any, exc: BaseException) -> str:
    if hasattr(adapter, "_error"):
        return adapter._error(exc)
    return str(exc)


@router.get("/brain/health")
def brain_health(request: Request, probe: bool = True) -> dict[str, Any]:
    """Return the explicit X8 brain ownership and OpenWebUI bridge health contract.

    This endpoint is intentionally strict. It reports OpenWebUI brain health; it
    does not use direct Ollama as a hidden success path when OpenWebUI is the
    configured conversational brain.
    """
    settings = request.app.state.settings
    provider = provider_name()
    adapter = build_adapter(settings)
    selected = selected_chat_model(settings)
    payload: dict[str, Any] = {
        "ok": False,
        "provider": provider,
        "conversation_memory_source": "openwebui" if provider in OPENWEBUI_PROVIDER_NAMES else "direct-provider",
        "operator_memory_source": "x8_receipts_and_audit_store",
        "hardcoded_chat_success_allowed": False,
        "selected_model": selected,
        "openwebui_base_url_configured": bool(getattr(adapter, "base_url", "")),
        "openwebui_api_key_configured": bool(getattr(adapter, "secret", "")),
        "openwebui_reachable": False,
        "openwebui_authenticated": False,
        "openwebui_models_visible": False,
        "ollama_models_visible_to_openwebui": False,
        "selected_model_available": False,
        "chat_completion_ok": False,
        "available_models": [],
        "endpoint_results": [],
        "failures": [],
    }

    if provider not in OPENWEBUI_PROVIDER_NAMES:
        payload["ok"] = True
        payload["failures"].append("OpenWebUI is not the selected chat provider.")
        return payload

    if not getattr(adapter, "base_url", ""):
        payload["failures"].append("OpenWebUI base URL is not configured.")
        return payload
    if not getattr(adapter, "secret", ""):
        payload["failures"].append("OpenWebUI API key is not configured.")
        return payload

    discovered: list[str] = []
    seen: set[str] = set()
    for path in ("/api/models", "/api/v1/models", "/ollama/api/tags"):
        result: dict[str, Any] = {"path": path, "ok": False, "models": [], "payload_shape": None, "error": ""}
        try:
            raw = adapter._json(path, timeout=8.0)
            payload["openwebui_reachable"] = True
            payload["openwebui_authenticated"] = True
            models = adapter._extract_models(raw)
            result["payload_shape"] = _shape(raw)
            result["models"] = models[:20]
            result["ok"] = True
            if models:
                payload["openwebui_models_visible"] = True
                if path == "/ollama/api/tags":
                    payload["ollama_models_visible_to_openwebui"] = True
                for model in models:
                    if model not in seen:
                        seen.add(model)
                        discovered.append(model)
        except urllib.error.HTTPError as exc:
            payload["openwebui_reachable"] = True
            if exc.code not in {401, 403}:
                payload["openwebui_authenticated"] = True
            result["error"] = _error(adapter, exc)
            payload["failures"].append(f"{path}: {result['error']}")
        except Exception as exc:
            result["error"] = _error(adapter, exc)
            payload["failures"].append(f"{path}: {result['error']}")
        payload["endpoint_results"].append(result)

    payload["available_models"] = discovered
    payload["selected_model_available"] = bool(selected and selected in discovered)
    if payload["openwebui_authenticated"] and not discovered:
        payload["failures"].append("OpenWebUI is authenticated but exposes zero models. Connect OpenWebUI to the Ollama backend and refresh its model inventory.")
    if discovered and selected and selected not in discovered:
        payload["failures"].append(f"Selected model '{selected}' is not present in OpenWebUI model inventory.")

    if probe and payload["selected_model_available"] and hasattr(adapter, "generate_with_metrics"):
        generation = adapter.generate_with_metrics(selected, settings.model_health_prompt, timeout_seconds=20.0)
        payload["chat_completion_ok"] = bool(generation.ok and "XV8_READY" in generation.content and not generation.fallback_used)
        payload["generation"] = {
            "ok": generation.ok,
            "model": generation.model,
            "fallback_used": generation.fallback_used,
            "timed_out": generation.timed_out,
            "timeout_seconds": generation.timeout_seconds,
            "failure_reason": generation.failure_reason,
            "content_preview": generation.content[:120],
        }
        if not payload["chat_completion_ok"]:
            payload["failures"].append(generation.failure_reason or "OpenWebUI health prompt did not return XV8_READY.")

    payload["ok"] = bool(
        payload["openwebui_reachable"]
        and payload["openwebui_authenticated"]
        and payload["openwebui_models_visible"]
        and payload["selected_model_available"]
        and (payload["chat_completion_ok"] if probe else True)
    )
    return payload
