from x8.operator.contracts import OperatorAuditEvent


class OperatorAudit:
    def event(self, event_type: str, summary: str, task_id: str = "", job_id: str = "", approval_id: str = "") -> OperatorAuditEvent:
        return OperatorAuditEvent(event_type=event_type, summary=summary, task_id=task_id, job_id=job_id, approval_id=approval_id, status="recorded")
