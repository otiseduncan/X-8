import hashlib
from datetime import datetime, timezone

from x8.operator.contracts import ApprovalStatus, OperatorAction, OperatorApprovalDecision, OperatorApprovalRequest


class OperatorApprovalService:
    def create(self, task_id: str, action: OperatorAction) -> OperatorApprovalRequest:
        return OperatorApprovalRequest(
            task_id=task_id,
            action_id=action.id,
            risk_level=action.risk_level,
            action_type=action.action_type,
            target_type=action.target_type,
            target_identifier=action.target_identifier,
            human_summary=f"Approve {action.action_type} for {action.target_identifier or action.target_type}.",
            technical_summary=f"Action hash {action.action_hash}; no execution occurs until approved.",
            before_state_summary="Not inspected in scaffold.",
            after_state_prediction="Mock/no-risk scaffold will not mutate state.",
            diff_or_preview=str(action.payload)[:2000],
            rollback_plan="No mutation is performed in this milestone.",
            execution_token_hash=self.token_hash(action.action_hash),
        )

    def decide(self, approval: OperatorApprovalRequest, decision: OperatorApprovalDecision) -> OperatorApprovalRequest:
        now = datetime.now(timezone.utc)
        if approval.expires_at <= now:
            approval.status = ApprovalStatus.EXPIRED
            return approval
        approval.decided_at = now
        approval.decided_by = decision.decided_by
        approval.decision = decision.decision
        approval.status = ApprovalStatus.APPROVED if decision.decision == "approve" else ApprovalStatus.DENIED
        return approval

    def token_hash(self, action_hash: str) -> str:
        return hashlib.sha256(f"operator-approval|{action_hash}".encode("utf-8")).hexdigest()
