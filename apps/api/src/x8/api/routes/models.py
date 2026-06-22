from fastapi import APIRouter, Query, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.chat import ModelStatus
from x8.contracts.receipts import Receipt
from x8.managers.brain_bridge_factory import build_adapter, provider_name, selected_chat_model
from x8.managers.model_manager import ModelReadinessManager
from x8.storage.postgres_store import PostgresStore

router = APIRouter(prefix="/api", tags=["models"])


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
