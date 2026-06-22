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
        return {"type": "dict", "keys": list(payload.keys())[:20]}
    return {"type": type(payload).__name__}


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
                endpoints.append(
                    {
                        "path": path,
                        "ok": bool(models),
                        "models_count": len(models),
                        "models_preview": models[:8],
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
