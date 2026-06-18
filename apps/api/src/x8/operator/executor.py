from x8.operator.contracts import ApprovalStatus, OperatorAction, OperatorActionResult, OperatorApprovalRequest, RiskLevel


class OperatorExecutor:
    def execute(self, action: OperatorAction, approval: OperatorApprovalRequest | None, mutations_enabled: bool) -> OperatorActionResult:
        if action.requires_approval and not approval:
            return OperatorActionResult(action_id=action.id, status="blocked", output_summary="Approval is required before execution.")
        if approval and approval.status != ApprovalStatus.APPROVED:
            return OperatorActionResult(action_id=action.id, status="blocked", output_summary=f"Approval status is {approval.status}.")
        if action.risk_level != RiskLevel.READ_ONLY and not mutations_enabled:
            return OperatorActionResult(action_id=action.id, status="blocked", output_summary="Operator mutations are disabled by kill switch.")
        if action.risk_level == RiskLevel.READ_ONLY:
            return OperatorActionResult(action_id=action.id, status="completed", output_summary="Read-only mock action completed.", output="No mutation performed.", mutated=False)
        return OperatorActionResult(action_id=action.id, status="completed", output_summary="Approved mutation mock completed without changing state.", output="Mock execution only.", mutated=False)
