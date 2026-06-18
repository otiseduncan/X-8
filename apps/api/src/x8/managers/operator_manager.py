from x8.contracts.approvals import RiskLevel
from x8.contracts.managers import ManagerContext, ManagerResponse, PlanStep
from x8.managers.approval_manager import ApprovalManager


class OperatorManager:
    name = "operator"
    version = "0.1.0"

    def __init__(self) -> None:
        self.approvals = ApprovalManager()

    def plan(self, context: ManagerContext) -> ManagerResponse:
        steps = [
            PlanStep(title="inspect", risk="safe_read"),
            PlanStep(title="plan", risk="safe_read"),
            PlanStep(title="propose patch", risk="safe_read"),
            PlanStep(title="click approval", risk="medium_change"),
            PlanStep(title="apply patch", risk="medium_change"),
            PlanStep(title="test preset", risk="low_change"),
            PlanStep(title="receipt", risk="safe_read"),
        ]
        return ManagerResponse(manager=self.name, message="Safe development loop prepared.", plan=steps)

    def propose_write(self, approved: bool = False) -> ManagerResponse:
        allowed, receipt = self.approvals.require("repo.write", RiskLevel.MEDIUM_CHANGE, approved)
        message = "Repo write allowed." if allowed else "Repo write denied without explicit approval."
        return ManagerResponse(manager=self.name, message=message, receipts=[receipt], data={"allowed": allowed})
