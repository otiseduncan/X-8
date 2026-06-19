from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from x8.brain.memory_manager import BrainMemoryManager
from x8.contracts.base import ResultEnvelope

router = APIRouter(prefix="/api/brain", tags=["brain"])


class FocusRequest(BaseModel):
    focus: str
    session_id: str = ""
    project_scope: str = ""
    session_scope: str = ""


class MemoryCreateRequest(BaseModel):
    content: str
    session_id: str = ""
    project_scope: str = ""
    session_scope: str = ""
    global_scope: bool = True


class MemoryPatchRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    active: bool | None = None
    soft_deleted: bool | None = None


class MemoryQueryRequest(BaseModel):
    query: str
    limit: int = 5
    project_scope: str = ""
    session_scope: str = ""


class CandidateExtractionRequest(BaseModel):
    text: str
    source_turn_id: str = ""
    source_tool: str = "chat"
    project_scope: str = ""
    session_scope: str = ""
    global_scope: bool = True


class AutoCaptureToggleRequest(BaseModel):
    enabled: bool


def _manager(request: Request) -> BrainMemoryManager:
    settings = request.app.state.settings
    return BrainMemoryManager(
        settings.database_url,
        memory_enabled=settings.brain_memory_enabled and settings.memory_enabled,
        global_enabled=settings.brain_memory_global_enabled,
        project_enabled=settings.brain_memory_project_enabled,
        session_enabled=settings.brain_memory_session_enabled,
        auto_capture_enabled=settings.memory_auto_capture_enabled,
        auto_capture_min_confidence=settings.memory_auto_capture_min_confidence,
        auto_capture_max_per_turn=settings.memory_auto_capture_max_per_turn,
        auto_capture_receipts_enabled=settings.memory_auto_capture_receipts_enabled,
    )


@router.get("/status", response_model=ResultEnvelope[dict[str, Any]])
def brain_status(request: Request) -> ResultEnvelope[dict[str, Any]]:
    data = _manager(request).status()
    return ResultEnvelope(ok=True, status="ready", data=data, message="Brain status loaded.")


@router.get("/focus", response_model=ResultEnvelope[dict[str, Any] | None])
def get_focus(request: Request, session_id: str = "", project_scope: str = "") -> ResultEnvelope[dict[str, Any] | None]:
    data = _manager(request).focus.get_focus(session_id=session_id, project_scope=project_scope)
    return ResultEnvelope(ok=True, status="ready" if data else "missing", data=data, message="Active focus loaded." if data else "No active focus saved yet.")


@router.post("/focus", response_model=ResultEnvelope[dict[str, Any]])
def set_focus(payload: FocusRequest, request: Request) -> ResultEnvelope[dict[str, Any]]:
    result = _manager(request).set_focus(payload.focus, session_id=payload.session_id, project_scope=payload.project_scope)
    return ResultEnvelope(ok=True, status=result.status, data=result.data["focus"], message=result.message, receipts=result.receipts)


@router.get("/memories", response_model=ResultEnvelope[list[dict[str, Any]]])
def list_memories(
    request: Request,
    q: str = "",
    status_filter: str = "",
    layer: str = "",
    type: str = "",
    project_scope: str = "",
    session_scope: str = "",
    include_deleted: bool = True,
) -> ResultEnvelope[list[dict[str, Any]]]:
    data = _manager(request).store.list_memories(include_deleted=include_deleted, query=q, status_filter=status_filter, layer=layer, memory_type=type, project_scope=project_scope, session_scope=session_scope)
    return ResultEnvelope(ok=True, status="ready", data=data, message=f"{len(data)} Brain memories found.")


@router.get("/candidates", response_model=ResultEnvelope[list[dict[str, Any]]])
def list_candidates(request: Request, decision: str = "", q: str = "", limit: int = 200) -> ResultEnvelope[list[dict[str, Any]]]:
    data = _manager(request).store.list_candidates(decision=decision, query=q, limit=limit)
    return ResultEnvelope(ok=True, status="ready", data=data, message=f"{len(data)} Brain memory candidates found.")


@router.post("/extract-candidates", response_model=ResultEnvelope[list[dict[str, Any]]])
def extract_candidates(payload: CandidateExtractionRequest, request: Request) -> ResultEnvelope[list[dict[str, Any]]]:
    manager = _manager(request)
    candidates = manager.extractor.extract(
        payload.text,
        source_turn_id=payload.source_turn_id,
        source_tool=payload.source_tool,
        project_scope=payload.project_scope,
        session_scope=payload.session_scope,
        global_scope=payload.global_scope,
    )
    data = [candidate.as_dict() | {"decision": manager.policy.decide_candidate(candidate, min_confidence=manager.auto_capture_min_confidence).decision} for candidate in candidates]
    return ResultEnvelope(ok=True, status="ready", data=data, message=f"{len(data)} candidates extracted.")


@router.post("/auto-capture/toggle", response_model=ResultEnvelope[dict[str, Any]])
def toggle_auto_capture(payload: AutoCaptureToggleRequest, request: Request) -> ResultEnvelope[dict[str, Any]]:
    data = _manager(request).set_auto_capture_enabled(payload.enabled)
    return ResultEnvelope(ok=True, status="updated", data=data, message=f"Auto-capture {'enabled' if payload.enabled else 'disabled'}.")


@router.get("/events", response_model=ResultEnvelope[list[dict[str, Any]]])
def list_events(request: Request, memory_id: str = "", event_type: str = "") -> ResultEnvelope[list[dict[str, Any]]]:
    data = _manager(request).store.list_events(memory_id=memory_id, event_type=event_type)
    return ResultEnvelope(ok=True, status="ready", data=data, message=f"{len(data)} Brain memory events found.")


@router.post("/memories", response_model=ResultEnvelope[dict[str, Any] | None])
def create_memory(payload: MemoryCreateRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).remember(payload.content, session_id=payload.session_id, project_scope=payload.project_scope, session_scope=payload.session_scope, global_scope=payload.global_scope)
    return ResultEnvelope(ok=result.status == "passed", status=result.status, data=result.data.get("memory"), message=result.message, receipts=result.receipts, errors=result.limitations)


@router.patch("/memories/{memory_id}", response_model=ResultEnvelope[dict[str, Any] | None])
def patch_memory(memory_id: str, payload: MemoryPatchRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    patch = {key: value for key, value in payload.model_dump().items() if value is not None}
    if "tags" in patch:
        import json

        patch["tags"] = json.dumps(patch["tags"])
    result = _manager(request).update_memory(memory_id, patch)
    return ResultEnvelope(ok=result.status != "blocked" and result.status != "missing", status=result.status, data=result.data.get("memory"), message=result.message, receipts=result.receipts)


@router.delete("/memories/{memory_id}", response_model=ResultEnvelope[dict[str, Any] | None])
def delete_memory(memory_id: str, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    data = _manager(request).store.soft_delete_memory(memory_id, source="api")
    return ResultEnvelope(ok=data is not None, status="deleted" if data else "missing", data=data, message="Brain memory deleted." if data else "Brain memory not found.")


@router.post("/memories/{memory_id}/approve", response_model=ResultEnvelope[dict[str, Any] | None])
def approve_memory(memory_id: str, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).approve(memory_id)
    return ResultEnvelope(ok=result.status != "missing", status=result.status, data=result.data.get("memory"), message=result.message, receipts=result.receipts)


@router.post("/memories/{memory_id}/reject", response_model=ResultEnvelope[dict[str, Any] | None])
def reject_memory(memory_id: str, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).reject(memory_id)
    return ResultEnvelope(ok=result.status != "missing", status=result.status, data=result.data.get("memory"), message=result.message, receipts=result.receipts)


@router.post("/memories/{memory_id}/reactivate", response_model=ResultEnvelope[dict[str, Any] | None])
def reactivate_memory(memory_id: str, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).reactivate(memory_id)
    return ResultEnvelope(ok=result.status != "missing", status=result.status, data=result.data.get("memory"), message=result.message, receipts=result.receipts)


@router.post("/remember", response_model=ResultEnvelope[dict[str, Any] | None])
def remember(payload: MemoryCreateRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).remember(payload.content, session_id=payload.session_id, project_scope=payload.project_scope, session_scope=payload.session_scope, global_scope=payload.global_scope)
    return ResultEnvelope(ok=result.status == "passed", status=result.status, data=result.data.get("memory"), message=result.message, receipts=result.receipts)


@router.post("/forget", response_model=ResultEnvelope[dict[str, Any] | None])
def forget(payload: MemoryQueryRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).forget(payload.query, project_scope=payload.project_scope, session_scope=payload.session_scope)
    return ResultEnvelope(ok=True, status=result.status, data=result.data.get("memory"), message=result.message, receipts=result.receipts)


@router.post("/retrieve", response_model=ResultEnvelope[list[dict[str, Any]]])
def retrieve(payload: MemoryQueryRequest, request: Request) -> ResultEnvelope[list[dict[str, Any]]]:
    result = _manager(request).retrieve(payload.query, limit=payload.limit, project_scope=payload.project_scope, session_scope=payload.session_scope)
    return ResultEnvelope(ok=True, status=result.status, data=result.data.get("memories", []), message=result.message, receipts=result.receipts)
