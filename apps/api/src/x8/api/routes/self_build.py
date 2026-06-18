from fastapi import APIRouter, HTTPException, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.self_build.contracts import PatchApplyRequest, PatchApplyResult, SelfBuildRequest, SelfBuildTask, SelfBuildValidationReport
from x8.self_build.manager import SelfBuildManager

router = APIRouter(prefix="/api/self-build", tags=["self_build"])
_managers: dict[str, SelfBuildManager] = {}


def manager(request: Request) -> SelfBuildManager:
    root = request.app.state.settings.workspace_root
    if root not in _managers:
        _managers[root] = SelfBuildManager(root)
    return _managers[root]


@router.post("/detect", response_model=ResultEnvelope[dict[str, object]])
def detect(payload: dict[str, str], request: Request) -> ResultEnvelope[dict[str, object]]:
    mgr = manager(request)
    prompt = payload.get("prompt", "")
    detected = mgr.detect(prompt)
    return ResultEnvelope(ok=True, status="detected" if detected else "not_detected", data={"self_build_prompt": detected, "intent": mgr.classify_intent(prompt)}, message="Self-build prompt detection completed.")


@router.post("/tasks", response_model=ResultEnvelope[SelfBuildTask])
def create_task(payload: SelfBuildRequest, request: Request) -> ResultEnvelope[SelfBuildTask]:
    task = manager(request).create_task(payload)
    return ResultEnvelope(
        ok=True,
        status=task.status,
        data=task,
        message="I detected a self-build prompt. I can inspect the repo and create a patch plan. No files will be changed until you approve.",
        receipts=[Receipt(action=item.action_type, status=item.status, summary=f"Self-build step: {item.action_type}", metadata=item.model_dump(mode="json")) for item in task.receipts],
    )


@router.post("/prompt", response_model=ResultEnvelope[dict[str, object]])
def handle_prompt(payload: dict[str, str], request: Request) -> ResultEnvelope[dict[str, object]]:
    mgr = manager(request)
    prompt = payload.get("prompt", "")
    intent = mgr.classify_intent(prompt)
    if intent == "create_proposal":
        task = mgr.create_task(SelfBuildRequest(user_prompt=prompt))
        detail = mgr.proposal_detail(task)
        return ResultEnvelope(
            ok=True,
            status="planned",
            data={"intent": intent, "task": task.model_dump(mode="json"), "proposal_detail": detail},
            message="No files changed. Approval required before apply.",
            receipts=[Receipt(action=item.action_type, status=item.status, summary=f"Self-build step: {item.action_type}", metadata=item.model_dump(mode="json")) for item in task.receipts],
        )
    if intent == "inspect_proposal":
        detail = mgr.latest_proposal_detail()
        if detail is None:
            return ResultEnvelope(ok=False, status="missing", data={"intent": intent}, message="No active self-build proposal found.")
        return ResultEnvelope(ok=True, status="proposed", data={"intent": intent, "proposal_detail": detail}, message="Self-build proposal details loaded.")
    if intent == "trust_status":
        return ResultEnvelope(ok=True, status="ready", data={"intent": intent, "trust_status": mgr.trust_status()}, message="Self-build trust gate status loaded.")
    if intent == "validation_report":
        report = mgr.latest_validation_report()
        if report is None:
            if mgr.latest_task() is None:
                return ResultEnvelope(ok=False, status="missing", data={"intent": intent}, message="No active self-build proposal found.")
            return ResultEnvelope(ok=False, status="missing", data={"intent": intent}, message="No active self-build validation report found.")
        return ResultEnvelope(ok=True, status=report.status, data={"intent": intent, "validation_report": report.model_dump(mode="json")}, message="Self-build validation report loaded.")
    if intent == "approval_apply":
        return ResultEnvelope(ok=False, status="approval_required", data={"intent": intent}, message="Use the locked apply endpoint with patch_id, approval_id, exact patch_hash, and approved=true.")
    return ResultEnvelope(ok=False, status="not_detected", data={"intent": intent}, message="No self-build intent detected.")


@router.get("/tasks/latest/proposal", response_model=ResultEnvelope[dict[str, object]])
def get_latest_proposal(request: Request) -> ResultEnvelope[dict[str, object]]:
    detail = manager(request).latest_proposal_detail()
    if detail is None:
        return ResultEnvelope(ok=False, status="missing", data={}, message="No active self-build proposal found.")
    return ResultEnvelope(ok=True, status="proposed", data=detail, message="Self-build latest proposal loaded.")


@router.get("/tasks/latest/validation", response_model=ResultEnvelope[dict[str, object]])
def get_latest_validation(request: Request) -> ResultEnvelope[dict[str, object]]:
    mgr = manager(request)
    report = mgr.latest_validation_report()
    if report is None:
        if mgr.latest_task() is None:
            return ResultEnvelope(ok=False, status="missing", data={}, message="No active self-build proposal found.")
        return ResultEnvelope(ok=False, status="missing", data={}, message="No active self-build validation report found.")
    return ResultEnvelope(ok=True, status=report.status, data=report.model_dump(mode="json"), message="Self-build latest validation report loaded.")


@router.get("/tasks/{task_id}", response_model=ResultEnvelope[SelfBuildTask])
def get_task(task_id: str, request: Request) -> ResultEnvelope[SelfBuildTask]:
    task = manager(request).get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Self-build task not found.")
    return ResultEnvelope(ok=True, status=task.status, data=task, message="Self-build task loaded.")


@router.get("/tasks/{task_id}/proposal", response_model=ResultEnvelope[dict[str, object]])
def get_task_proposal(task_id: str, request: Request) -> ResultEnvelope[dict[str, object]]:
    task = manager(request).get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Self-build task not found.")
    if task.proposal is None:
        return ResultEnvelope(ok=False, status="missing", data={}, message="No active self-build proposal found.")
    return ResultEnvelope(ok=True, status=task.proposal.status, data=manager(request).proposal_detail(task), message="Self-build patch proposal loaded.")


@router.post("/tasks/{task_id}/apply", response_model=ResultEnvelope[PatchApplyResult])
def apply_patch(task_id: str, payload: PatchApplyRequest, request: Request) -> ResultEnvelope[PatchApplyResult]:
    try:
        result = manager(request).apply_patch(task_id, payload)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ResultEnvelope(
        ok=result.applied,
        status=result.status,
        data=result,
        message=result.reason,
        receipts=[Receipt(action="self_build.patch_apply", status=result.status, summary=result.reason, metadata=result.model_dump(mode="json"))],
    )


@router.post("/tasks/{task_id}/validate", response_model=ResultEnvelope[SelfBuildValidationReport])
def validate_task(task_id: str, request: Request) -> ResultEnvelope[SelfBuildValidationReport]:
    try:
        report = manager(request).validate_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ResultEnvelope(
        ok=report.validation_passed,
        status=report.status,
        data=report,
        message="Self-build validation completed." if report.validation_passed else report.failure_reason,
        receipts=[Receipt(action="self_build.validation", status=report.status, summary=report.failure_reason or "Validation presets passed.", metadata=report.model_dump(mode="json"))],
    )


@router.get("/trust-status", response_model=ResultEnvelope[dict[str, object]])
def trust_status(request: Request) -> ResultEnvelope[dict[str, object]]:
    data = manager(request).trust_status()
    return ResultEnvelope(ok=True, status=str(data["status"]), data=data, message="Self-build trust gate status loaded.")
