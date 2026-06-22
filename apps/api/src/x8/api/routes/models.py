from fastapi import APIRouter, Query, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.chat import ModelStatus
from x8.contracts.receipts import Receipt
from x8.managers.brain_bridge_factory import build_adapter, provider_name, selected_chat_model
from x8.managers.model_manager import ModelReadinessManager
from x8.storage.postgres_store import PostgresStore

router = APIRouter(prefix="/api", tags=["models"])


def _payload_shape(payload):
    if isinstance(payload, list):
        return {"type": "list", "length": len(payload)}
    if isinstance(payload, dict):
        shape = {"type": "dict", "keys": list(payload.keys())[:20]}
        data = payload.get("data")
        if isinstance(data, list):
            shape["data_type"] = "list"
            shape["data_length"] = len(data)
            if data and isinstance(data[0], dict):
                shape["first_data_keys"] = list(data[0].keys())[:20]
        elif isinstance(data, dict):
            shape["data_type"] = "dict"
            shape["data_keys_preview"] = list(data.keys())[:20]
            for nested_key in ("models", "items", "results"):
                nested = data.get(nested_key)
                if isinstance(nested, list):
                    shape[f"data_{nested_key}_length"] = len(nested)
                    if nested and isinstance(nested[0], dict):
                        shape[f"first_data_{nested_key}_keys"] = list(nested[0].keys())[:20]
        models = payload.get("models")
        if isinstance(models, list):
            shape["models_length"] = len(models)
            if models and isinstance(models[0], dict):
                shape["first_models_keys"] = list(models[0].keys())[:20]
        message = payload.get("message")
        if isinstance(message, dict):
            shape["message_keys"] = list(message.keys())[:20]
        choices = payload.get("choices")
        if isinstance(choices, list):
            shape["choices_length"] = len(choices)
            if choices and isinstance(choices[0], dict):
                shape["first_choice_keys"] = list(choices[0].keys())[:20]
        return shape
    return {"type": type(payload).__name__}


def _safe_preview(value: str, limit: int = 400) -> str:
    return " ".join((value or "")[:limit].split())


@router.get("/models/status", response_model=ResultEnvelope[ModelStatus])
def model_status(request: Request, probe: bool = Query(False, description="Run an actual XV8_READY generation probe.")) -> ResultEnvelope[ModelStatus]:
    settings = request.app.state.settings
    status = ModelReadinessManager(
        build_adapter(settings),
        selected_chat_model(settings),
        settings.fallback_chat_model,
        ollama_mode=f"{provider_name()}:{settings.ollama_mode}",
        reasoning_model=settings.reasoning_model,
        code_model=settings.code_model,
        embedding_model=settings.embedding_model,
        health_prompt=settings.model_health_prompt,
        embedding_required_for_memory=settings.embedding_required_for_memory,
    ).status(probe=probe)
    PostgresStore(settings.database_url).insert_model_status(status.model_dump())
    status_label = "ready" if status.model_ready else "unavailable"
    action = "model_status_probe" if probe else "model_status_check"
    summary = "Brain bridge model readiness probed." if probe else "Brain bridge model availability checked without generation."
    return ResultEnvelope(
        ok=True,
        status=status_label,
        data=status,
        message="Model provider probed." if probe else "Model provider checked without generation.",
        receipts=[
            Receipt(
                action=action,
                status=status_label,
                summary=summary,
                metadata={
                    "probe": probe,
                    "provider": provider_name(),
                    "selected_model": status.selected_model,
                    "fallback_used": status.fallback_used,
                    "failure_reason": status.failure_reason,
                },
            )
        ],
    )


@router.get("/models/bridge-diagnostics")
def bridge_diagnostics(request: Request):
    """Return sanitized model-provider diagnostics without exposing auth material."""
    settings = request.app.state.settings
    adapter = build_adapter(settings)
    endpoints = []
    if hasattr(adapter, "base_url") and hasattr(adapter, "_json"):
        for path in ("/api/models", "/api/v1/models", "/v1/models", "/ollama/api/tags"):
            try:
                payload = adapter._json(path, timeout=8.0)
                models = adapter._extract_models(payload) if hasattr(adapter, "_extract_models") else []
                payload_error = adapter._payload_error(payload) if hasattr(adapter, "_payload_error") else ""
                reachable_sparse = False
                if hasattr(adapter, "_payload_has_success_shape"):
                    reachable_sparse = bool(adapter._payload_has_success_shape(payload) and not models and getattr(adapter, "default_model", ""))
                endpoints.append(
                    {
                        "path": path,
                        "ok": bool(models) or reachable_sparse,
                        "models_count": len(models),
                        "models_preview": models[:8],
                        "reachable_sparse_catalog": reachable_sparse,
                        "configured_default_usable": getattr(adapter, "default_model", "") if reachable_sparse else "",
                        "payload_shape": _payload_shape(payload),
                        "payload_error": payload_error,
                    }
                )
            except Exception as exc:
                error = adapter._error(exc) if hasattr(adapter, "_error") else str(exc)
                endpoints.append({"path": path, "ok": False, "error": error[:1000]})
        return {
            "ok": True,
            "provider": provider_name(),
            "bridge_base_url_configured": bool(getattr(adapter, "base_url", "")),
            "auth_configured": bool(getattr(adapter, "secret", "")),
            "default_model": getattr(adapter, "default_model", ""),
            "model_discovery_note": getattr(adapter, "last_model_discovery_note", ""),
            "endpoints": endpoints,
        }
    ok, models, reason = adapter.models()
    return {
        "ok": True,
        "provider": provider_name(),
        "bridge_base_url_configured": False,
        "auth_configured": False,
        "default_model": selected_chat_model(settings),
        "fallback_models_ok": ok,
        "models_preview": models[:8],
        "reason": reason,
    }


@router.get("/models/bridge-chat-diagnostics")
def bridge_chat_diagnostics(
    request: Request,
    model: str = Query("", max_length=180),
    prompt: str = Query("Reply with XV8_READY only.", max_length=240),
):
    """Run targeted sanitized completion probes against the model bridge."""
    settings = request.app.state.settings
    adapter = build_adapter(settings)
    selected = (model or selected_chat_model(settings)).strip()
    attempts = []
    if not (hasattr(adapter, "_json") and hasattr(adapter, "_completion_attempts")):
        return {
            "ok": False,
            "provider": provider_name(),
            "reason": "Selected adapter does not expose bridge diagnostics.",
        }

    candidate_models = adapter._candidate_models(selected) if hasattr(adapter, "_candidate_models") else [selected]
    targeted_paths = {"/ollama/api/chat", "/ollama/api/generate", "/api/chat/completions", "/api/v1/chat/completions"}
    for candidate in candidate_models[:6]:
        for path, body in adapter._completion_attempts(candidate, prompt):
            if path not in targeted_paths:
                continue
            try:
                payload = adapter._json(path, method="POST", body=body, timeout=30.0)
                content = adapter._content(payload) if hasattr(adapter, "_content") else ""
                payload_error = adapter._payload_error(payload) if hasattr(adapter, "_payload_error") else ""
                item = {
                    "model": candidate,
                    "path": path,
                    "ok": bool(content),
                    "content_preview": _safe_preview(content),
                    "payload_shape": _payload_shape(payload),
                    "payload_error": payload_error,
                }
                attempts.append(item)
                if content:
                    return {
                        "ok": True,
                        "provider": provider_name(),
                        "selected_model": selected,
                        "working_model": candidate,
                        "working_path": path,
                        "attempts": attempts,
                    }
            except Exception as exc:
                error = adapter._error(exc) if hasattr(adapter, "_error") else str(exc)
                attempts.append(
                    {
                        "model": candidate,
                        "path": path,
                        "ok": False,
                        "error": error[:1000],
                    }
                )
    return {
        "ok": False,
        "provider": provider_name(),
        "selected_model": selected,
        "candidate_models": candidate_models[:6],
        "attempts": attempts,
    }
