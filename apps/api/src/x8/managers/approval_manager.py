from x8.contracts.approvals import ActionIntent, ApprovalDecision, ApprovalRequest, ApprovalStatus, RiskLevel, RollbackHint
from x8.contracts.receipts import Receipt


class ApprovalManager:
    name = "approval"
    version = "0.1.0"

    def require(self, action: str, risk: RiskLevel, approved: bool = False) -> tuple[bool, Receipt]:
        status = "approved" if approved else "blocked"
        receipt = Receipt(
            action=action,
            status=status,
            summary=f"{action} requires explicit approval at {risk.value} risk.",
            metadata={"risk": risk.value},
        )
        return approved, receipt

    def request(self, action: str, risk: RiskLevel, intent: ActionIntent, rollback_hint: RollbackHint, reason: str) -> ApprovalRequest:
        return ApprovalRequest(action=action, risk=risk, reason=reason, intent=intent, rollback_hint=rollback_hint)


class ApprovalModalManager:
    name = "approval_modal"
    version = "0.1.0"

    def __init__(self) -> None:
        self._pending: dict[str, ApprovalRequest] = {}

    def queue(self, request: ApprovalRequest) -> ApprovalRequest:
        self._pending[request.id] = request
        return request

    def pending(self) -> list[ApprovalRequest]:
        return list(self._pending.values())

    def decide(self, decision: ApprovalDecision) -> ApprovalRequest:
        request = self._pending[decision.approval_id]
        request.status = ApprovalStatus.APPROVED if decision.approved_by_user_click else ApprovalStatus.CANCELLED
        request.approved = decision.approved_by_user_click
        if not decision.approved_by_user_click:
            request.reason = decision.cancel_reason or "Cancelled by user click."
        return request


approval_modal_manager = ApprovalModalManager()
