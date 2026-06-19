from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from x8.brain.continuity_manager import BrainContinuityManager
from x8.contracts.base import ResultEnvelope

router = APIRouter(prefix="/api/brain/continuity", tags=["brain-continuity"])


class ContinuityRecordRequest(BaseModel):
    record_type: str = "task"
    title: str = ""
    summary: str = ""
    content: str = ""
    status: str = "active"
    priority: str = "normal"
    project_scope: str = ""
    session_scope: str = ""
    global_scope: bool = True
    linked_memory_id: str = ""
    linked_commit_sha: str = ""
    linked_validation_event: str = ""


class ContinuityPatchRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    status: str | None = None
    priority: str | None = None
    active: bool | None = None
    soft_deleted: bool | None = None
    project_scope: str | None = None
    session_scope: str | None = None
    global_scope: bool | None = None


class SummaryRequest(BaseModel):
    summary: str = ""
    content: str = ""
    project_scope: str = ""
    session_scope: str = ""
    global_scope: bool = True


def _manager(request: Request) -> BrainContinuityManager:
    return BrainContinuityManager(request.app.state.settings.database_url)


@router.get("/status", response_model=ResultEnvelope[dict[str, Any]])
def status(request: Request, project_scope: str = "", session_scope: str = "") -> ResultEnvelope[dict[str, Any]]:
    data = _manager(request).status(project_scope=project_scope, session_scope=session_scope)
    return ResultEnvelope(ok=True, status="ready", data=data, message="Brain continuity status loaded.")


@router.get("/records", response_model=ResultEnvelope[list[dict[str, Any]]])
def records(request: Request, record_type: str = "", status: str = "", project_scope: str = "", session_scope: str = "", include_deleted: bool = False, q: str = "") -> ResultEnvelope[list[dict[str, Any]]]:
    data = _manager(request).records(record_type=record_type, status=status, project_scope=project_scope, session_scope=session_scope, include_deleted=include_deleted, query=q)
    return ResultEnvelope(ok=True, status="ready", data=data, message=f"{len(data)} continuity records found.")


@router.post("/records", response_model=ResultEnvelope[dict[str, Any] | None])
def create_record(payload: ContinuityRecordRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).create_record(payload.model_dump())
    return ResultEnvelope(ok=result.status != "blocked", status=result.status, data=result.data.get("record"), message=result.message, receipts=result.receipts)


@router.patch("/records/{record_id}", response_model=ResultEnvelope[dict[str, Any] | None])
def update_record(record_id: str, payload: ContinuityPatchRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    patch = {key: value for key, value in payload.model_dump().items() if value is not None}
    result = _manager(request).update_record(record_id, patch)
    return ResultEnvelope(ok=result.status not in {"blocked", "missing"}, status=result.status, data=result.data.get("record"), message=result.message, receipts=result.receipts)


@router.delete("/records/{record_id}", response_model=ResultEnvelope[dict[str, Any] | None])
def delete_record(record_id: str, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).archive_record(record_id)
    return ResultEnvelope(ok=result.status != "missing", status=result.status, data=result.data.get("record"), message=result.message, receipts=result.receipts)


@router.get("/tasks", response_model=ResultEnvelope[list[dict[str, Any]]])
def tasks(request: Request, status: str = "", project_scope: str = "", session_scope: str = "") -> ResultEnvelope[list[dict[str, Any]]]:
    data = _manager(request).records(record_type="task", status=status, project_scope=project_scope, session_scope=session_scope)
    return ResultEnvelope(ok=True, status="ready", data=data, message=f"{len(data)} continuity tasks found.")


@router.post("/tasks", response_model=ResultEnvelope[dict[str, Any] | None])
def create_task(payload: SummaryRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).create_task(payload.summary or payload.content, project_scope=payload.project_scope, session_scope=payload.session_scope, global_scope=payload.global_scope)
    return ResultEnvelope(ok=result.status != "blocked", status=result.status, data=result.data.get("record"), message=result.message, receipts=result.receipts)


@router.patch("/tasks/{record_id}", response_model=ResultEnvelope[dict[str, Any] | None])
def update_task(record_id: str, payload: ContinuityPatchRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    return update_record(record_id, payload, request)


@router.delete("/tasks/{record_id}", response_model=ResultEnvelope[dict[str, Any] | None])
def delete_task(record_id: str, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    return delete_record(record_id, request)


@router.get("/project-state", response_model=ResultEnvelope[dict[str, Any] | None])
def project_state(request: Request, project_scope: str = "", session_scope: str = "") -> ResultEnvelope[dict[str, Any] | None]:
    data = _manager(request).current_project(project_scope=project_scope, session_scope=session_scope)
    return ResultEnvelope(ok=True, status="ready" if data else "missing", data=data, message="Current project state loaded." if data else "No current project state saved.")


@router.post("/project-state", response_model=ResultEnvelope[dict[str, Any] | None])
def set_project_state(payload: SummaryRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).set_project_state(payload.summary or payload.content, project_scope=payload.project_scope, session_scope=payload.session_scope, global_scope=payload.global_scope)
    return ResultEnvelope(ok=result.status != "blocked", status=result.status, data=result.data.get("record"), message=result.message, receipts=result.receipts)


@router.get("/blockers", response_model=ResultEnvelope[list[dict[str, Any]]])
def blockers(request: Request, project_scope: str = "", session_scope: str = "") -> ResultEnvelope[list[dict[str, Any]]]:
    data = _manager(request).records(record_type="blocker", status="active", project_scope=project_scope, session_scope=session_scope)
    return ResultEnvelope(ok=True, status="ready", data=data, message=f"{len(data)} active blockers found.")


@router.post("/blockers", response_model=ResultEnvelope[dict[str, Any] | None])
def add_blocker(payload: SummaryRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).add_blocker(payload.summary or payload.content, project_scope=payload.project_scope, session_scope=payload.session_scope, global_scope=payload.global_scope)
    return ResultEnvelope(ok=result.status != "blocked", status=result.status, data=result.data.get("record"), message=result.message, receipts=result.receipts)


@router.get("/checkpoints", response_model=ResultEnvelope[list[dict[str, Any]]])
def checkpoints(request: Request, project_scope: str = "", session_scope: str = "") -> ResultEnvelope[list[dict[str, Any]]]:
    manager = _manager(request)
    data = manager.records(record_type="validation_checkpoint", project_scope=project_scope, session_scope=session_scope) + manager.records(record_type="commit_checkpoint", project_scope=project_scope, session_scope=session_scope)
    return ResultEnvelope(ok=True, status="ready", data=data, message=f"{len(data)} checkpoints found.")


@router.post("/checkpoints", response_model=ResultEnvelope[dict[str, Any] | None])
def add_checkpoint(payload: SummaryRequest, request: Request) -> ResultEnvelope[dict[str, Any] | None]:
    result = _manager(request).add_validation(payload.summary or payload.content, project_scope=payload.project_scope, session_scope=payload.session_scope, global_scope=payload.global_scope)
    return ResultEnvelope(ok=result.status != "blocked", status=result.status, data=result.data.get("record"), message=result.message, receipts=result.receipts)


@router.post("/handoff", response_model=ResultEnvelope[dict[str, Any]])
def handoff(payload: SummaryRequest, request: Request) -> ResultEnvelope[dict[str, Any]]:
    result = _manager(request).handoff(project_scope=payload.project_scope, session_scope=payload.session_scope)
    return ResultEnvelope(ok=True, status=result.status, data=result.data, message=result.message, receipts=result.receipts)
