from fastapi import APIRouter, HTTPException, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.operator.contracts import OperatorTaskRequest
from x8.operator.runtime import OperatorRuntime

router = APIRouter(prefix="/api/operator", tags=["operator"])
_state: dict[str, dict[str, object]] = {"tasks": {}, "jobs": {}, "approvals": {}, "audit": []}


def runtime(request: Request) -> OperatorRuntime:
    return OperatorRuntime(request.app.state.settings)


@router.post("/tasks", response_model=ResultEnvelope[dict[str, object]])
def create_task(payload: OperatorTaskRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    result = runtime(request).create_task(payload)
    task = result["task"]
    job = result["job"]
    _state["tasks"][task.id] = result
    if job:
        _state["jobs"][job.id] = result
    for approval in result["approvals"]:
        _state["approvals"][approval.id] = approval
    _state["audit"].extend(result["audit"])
    return ResultEnvelope(ok=True, status=task.status, data=result, message="Operator task scaffold created.", receipts=[Receipt(action="operator.task_created", status=task.status, summary="Operator task scaffold created.")])


@router.get("/tasks/{task_id}", response_model=ResultEnvelope[dict[str, object]])
def get_task(task_id: str) -> ResultEnvelope[dict[str, object]]:
    result = _state["tasks"].get(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Operator task not found.")
    return ResultEnvelope(ok=True, status="loaded", data=result, message="Operator task loaded.")


@router.post("/tasks/{task_id}/cancel", response_model=ResultEnvelope[dict[str, str]])
def cancel_task(task_id: str) -> ResultEnvelope[dict[str, str]]:
    if task_id not in _state["tasks"]:
        raise HTTPException(status_code=404, detail="Operator task not found.")
    return ResultEnvelope(ok=True, status="cancelled", data={"task_id": task_id}, message="Operator task cancelled before real execution.")


@router.get("/jobs", response_model=ResultEnvelope[list[object]])
def list_jobs() -> ResultEnvelope[list[object]]:
    return ResultEnvelope(ok=True, status="ready", data=list(_state["jobs"].values()), message="Operator jobs listed.")


@router.get("/jobs/{job_id}", response_model=ResultEnvelope[dict[str, object]])
def get_job(job_id: str) -> ResultEnvelope[dict[str, object]]:
    result = _state["jobs"].get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Operator job not found.")
    return ResultEnvelope(ok=True, status="loaded", data=result, message="Operator job loaded.")


@router.post("/jobs/{job_id}/cancel", response_model=ResultEnvelope[dict[str, str]])
def cancel_job(job_id: str) -> ResultEnvelope[dict[str, str]]:
    if job_id not in _state["jobs"]:
        raise HTTPException(status_code=404, detail="Operator job not found.")
    return ResultEnvelope(ok=True, status="cancelled", data={"job_id": job_id}, message="Operator job cancelled before real execution.")


@router.get("/approvals", response_model=ResultEnvelope[list[object]])
def list_approvals() -> ResultEnvelope[list[object]]:
    return ResultEnvelope(ok=True, status="ready", data=list(_state["approvals"].values()), message="Operator approvals listed.")


@router.get("/approvals/{approval_id}", response_model=ResultEnvelope[object])
def get_approval(approval_id: str) -> ResultEnvelope[object]:
    approval = _state["approvals"].get(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Operator approval not found.")
    return ResultEnvelope(ok=True, status="loaded", data=approval, message="Operator approval loaded.")


@router.post("/approvals/{approval_id}/approve", response_model=ResultEnvelope[dict[str, str]])
def approve(approval_id: str) -> ResultEnvelope[dict[str, str]]:
    return ResultEnvelope(ok=True, status="mock_only", data={"approval_id": approval_id}, message="Approval decision scaffolded; no real action executed.")


@router.post("/approvals/{approval_id}/deny", response_model=ResultEnvelope[dict[str, str]])
def deny(approval_id: str) -> ResultEnvelope[dict[str, str]]:
    return ResultEnvelope(ok=True, status="denied", data={"approval_id": approval_id}, message="Approval denied; no action executed.")


@router.get("/audit", response_model=ResultEnvelope[list[object]])
def audit() -> ResultEnvelope[list[object]]:
    return ResultEnvelope(ok=True, status="ready", data=_state["audit"], message="Operator audit events listed.")


@router.get("/capabilities", response_model=ResultEnvelope[list[object]])
def capabilities(request: Request) -> ResultEnvelope[list[object]]:
    return ResultEnvelope(ok=True, status="ready", data=runtime(request).capabilities(), message="Operator capabilities loaded.")
