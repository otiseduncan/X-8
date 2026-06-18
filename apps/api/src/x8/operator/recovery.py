from x8.operator.contracts import OperatorRecoveryPlan


class OperatorRecovery:
    def plan(self, task_id: str) -> OperatorRecoveryPlan:
        return OperatorRecoveryPlan(task_id=task_id, status="not_required", summary="No recovery is required for read-only/mock scaffold actions.")
