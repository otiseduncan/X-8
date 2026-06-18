from x8.operator.approvals import OperatorApprovalService
from x8.operator.audit import OperatorAudit
from x8.operator.contracts import OperatorResourceBudget, OperatorTaskRequest, RiskLevel
from x8.operator.executor import OperatorExecutor
from x8.operator.jobs import OperatorJobEngine
from x8.operator.observer import OperatorObserver
from x8.operator.planner import OperatorPlanner
from x8.operator.registry import default_operator_registry
from x8.operator.resources import ResourceGuard
from x8.operator.verifier import OperatorVerifier


class OperatorRuntime:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.budget = OperatorResourceBudget(
            max_runtime_seconds=settings.operator_max_runtime_seconds,
            max_output_chars=settings.operator_max_output_chars,
            max_file_bytes=settings.operator_max_file_bytes,
            max_context_chars=settings.operator_max_context_chars,
            max_parallel_jobs=settings.operator_max_parallel_jobs,
            tool_timeout_seconds=settings.operator_tool_timeout_seconds,
        )
        self.guard = ResourceGuard(self.budget)
        self.registry = default_operator_registry()
        self.planner = OperatorPlanner()
        self.approvals = OperatorApprovalService()
        self.executor = OperatorExecutor()
        self.observer = OperatorObserver(self.guard)
        self.jobs = OperatorJobEngine()
        self.audit = OperatorAudit()
        self.verifier = OperatorVerifier()

    def create_task(self, request: OperatorTaskRequest) -> dict[str, object]:
        if not self.settings.operator_enabled:
            task = self.planner.plan(request)
            task.status = "blocked"
            task.limitations.append("Operator runtime is disabled.")
            return {"task": task, "job": None, "approvals": [], "observations": [], "results": [], "audit": []}
        task = self.planner.plan(request)
        action = task.actions[0]
        approvals = [self.approvals.create(task.id, action)] if action.requires_approval else []
        observations = []
        results = []
        if not action.requires_approval and action.risk_level == RiskLevel.READ_ONLY:
            observations.append(self.observer.mock_observation("model_status", action.target_identifier or "operator", "Read-only scaffold observation completed."))
            results.append(self.executor.execute(action, None, self.settings.operator_mutations_enabled))
        job = self.jobs.create(task.id, waiting_for_approval=bool(approvals))
        task.job_id = job.id
        audit = [self.audit.event("operator_task_created", f"Task {task.id} created.", task_id=task.id, job_id=job.id)]
        return {"task": task, "job": job, "approvals": approvals, "observations": observations, "results": results, "audit": audit}

    def capabilities(self):
        caps = self.registry.capabilities()
        if not self.settings.operator_mutations_enabled:
            for cap in caps:
                if cap.risk_level != RiskLevel.READ_ONLY:
                    cap.status = "blocked"
                    cap.limitations.append("Mutations are disabled by kill switch.")
        return caps
