from pydantic import BaseModel
from fastapi import APIRouter

from x8.contracts.approvals import ActionIntent, ApprovalDecision, ApprovalRequest, RiskLevel, RollbackHint
from x8.contracts.base import ResultEnvelope
from x8.managers.approval_manager import ApprovalManager, approval_modal_manager

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ApprovalCreateRequest(BaseModel):
    action: str
    risk: RiskLevel
    target: str
    summary: str
    destructive: bool = False


@router.get("/pending", response_model=ResultEnvelope[list[ApprovalRequest]])
def pending() -> ResultEnvelope[list[ApprovalRequest]]:
    return ResultEnvelope(ok=True, status="implemented", data=approval_modal_manager.pending(), message="Pending click approvals listed.")


@router.post("/request", response_model=ResultEnvelope[ApprovalRequest])
def request_approval(payload: ApprovalCreateRequest) -> ResultEnvelope[ApprovalRequest]:
    risk = RiskLevel.DESTRUCTIVE if payload.destructive else payload.risk
    approval = ApprovalManager().request(
        action=payload.action,
        risk=risk,
        intent=ActionIntent(action=payload.action, files_affected=[payload.target], summary=payload.summary, will_change_files=risk != RiskLevel.SAFE_READ),
        rollback_hint=RollbackHint(summary=f"Rollback depends on the action target: {payload.target}", reversible=not payload.destructive),
        reason="Click approval requested.",
    )
    approval_modal_manager.queue(approval)
    return ResultEnvelope(ok=True, status="pending_click", data=approval, message="Approval queued for modal display.")


@router.post("/decision", response_model=ResultEnvelope[ApprovalRequest])
def decision(payload: ApprovalDecision) -> ResultEnvelope[ApprovalRequest]:
    approval = approval_modal_manager.decide(payload)
    status = "approved" if approval.approved else "cancelled"
    return ResultEnvelope(ok=True, status=status, data=approval, message=f"Approval {status} by user click.")
