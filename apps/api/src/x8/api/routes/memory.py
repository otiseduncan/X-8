from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.memory_manager import MemoryApprovalDecision, MemoryManager, MemoryProposal, MemoryRecord, MemoryStatus
from x8.managers.model_manager import ModelReadinessManager, OllamaAdapter

router = APIRouter(prefix="/api", tags=["memory"])


def _model_status(request: Request):
    settings = request.app.state.settings
    return ModelReadinessManager(
        OllamaAdapter(settings.ollama_base_url),
        settings.default_chat_model,
        settings.fallback_chat_model,
        ollama_mode=settings.ollama_mode,
        reasoning_model=settings.reasoning_model,
        code_model=settings.code_model,
        embedding_model=settings.embedding_model,
        health_prompt=settings.model_health_prompt,
        embedding_required_for_memory=settings.embedding_required_for_memory,
    ).status()


def _manager(request: Request) -> MemoryManager:
    return MemoryManager(request.app.state.settings.memory_storage_path)


@router.get("/memory/status", response_model=ResultEnvelope[MemoryStatus])
def memory_status(request: Request) -> ResultEnvelope[MemoryStatus]:
    settings = request.app.state.settings
    model_status = _model_status(request)
    vector_ready = True
    failure = ""
    if not model_status.embedding_ready:
        failure = f"Embedding model unavailable: {settings.embedding_model}"
    data = _manager(request).status(settings.memory_enabled, settings.embedding_model, model_status.embedding_ready, vector_ready, failure)
    return ResultEnvelope(
        ok=True,
        status="ready" if data.memory_ready else "unavailable",
        data=data,
        message="Memory readiness checked.",
        receipts=[
            Receipt(
                action="memory_status_check",
                status="ready" if data.memory_ready else "unavailable",
                summary="Memory readiness checked without activating unapproved records.",
                metadata={"embedding_model": data.embedding_model, "embedding_ready": data.embedding_ready, "memory_ready": data.memory_ready, "failure_reason": data.failure_reason},
            )
        ],
    )


@router.get("/memory/records", response_model=ResultEnvelope[list[MemoryRecord]])
def memory_records(request: Request) -> ResultEnvelope[list[MemoryRecord]]:
    records = _manager(request).writer.load()
    return ResultEnvelope(ok=True, status="ready", data=records, message="Memory records loaded.")


@router.post("/memory/proposals", response_model=ResultEnvelope[MemoryRecord | None])
def create_memory_proposal(proposal: MemoryProposal, request: Request) -> ResultEnvelope[MemoryRecord | None]:
    record, receipt = _manager(request).propose(proposal)
    ok = record is not None
    return ResultEnvelope(
        ok=ok,
        status=receipt.status,
        data=record,
        message="Memory proposal created." if ok else "Memory proposal blocked.",
        receipts=[Receipt(action=receipt.action_type, status=receipt.status, summary="Memory proposal handled.", metadata=receipt.model_dump())],
        errors=receipt.limitations,
    )


@router.post("/memory/approvals", response_model=ResultEnvelope[MemoryRecord | None])
def approve_memory(decision: MemoryApprovalDecision, request: Request) -> ResultEnvelope[MemoryRecord | None]:
    record, receipt = _manager(request).approve(decision)
    return ResultEnvelope(
        ok=record is not None,
        status=receipt.status,
        data=record,
        message="Memory approval decision applied.",
        receipts=[Receipt(action=receipt.action_type, status=receipt.status, summary="Memory approval decision applied.", metadata=receipt.model_dump())],
    )


@router.get("/memory/search", response_model=ResultEnvelope[list[dict[str, object]]])
def search_memory(q: str, request: Request) -> ResultEnvelope[list[dict[str, object]]]:
    results, receipt = _manager(request).recall(q)
    data = [{"memory_record_id": item.record.memory_record_id, "text": item.record.text, "memory_type": item.record.memory_type, "source": item.record.source, "score": item.score, "match_type": item.match_type} for item in results]
    return ResultEnvelope(
        ok=True,
        status="ready" if data else "no_matches",
        data=data,
        message="Memory search completed.",
        receipts=[Receipt(action=receipt.action_type, status=receipt.status, summary="Memory recall completed.", metadata=receipt.model_dump())],
    )
