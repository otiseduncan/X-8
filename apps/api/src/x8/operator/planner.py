import hashlib

from x8.operator.contracts import OperatorAction, OperatorPlan, OperatorPlanStep, OperatorTask, OperatorTaskRequest
from x8.operator.risk import RiskAssessor


class OperatorPlanner:
    def __init__(self, risk: RiskAssessor | None = None) -> None:
        self.risk = risk or RiskAssessor()

    def plan(self, request: OperatorTaskRequest) -> OperatorTask:
        action_type = self._action_type(request)
        assessment = self.risk.assess(action_type)
        action = OperatorAction(
            task_id="pending",
            action_type=action_type,
            target_type=request.target_type,
            target_identifier=request.target_identifier,
            risk_level=assessment.risk_level,
            requires_approval=assessment.requires_approval,
            action_hash=self._hash(action_type, request.target_identifier, request.prompt),
            payload={"prompt": request.prompt, "dry_run": request.dry_run},
        )
        task = OperatorTask(session_id=request.session_id, prompt=request.prompt, source=request.source, status="planned")
        action.task_id = task.id
        step = OperatorPlanStep(title=f"Plan {action_type}", action_type=action_type, risk_level=assessment.risk_level, requires_approval=assessment.requires_approval)
        task.plan = OperatorPlan(task_id=task.id, summary=f"{action_type} planned with risk {assessment.risk_level}.", steps=[step])
        task.actions = [action]
        if action_type == "arbitrary_shell":
            task.status = "blocked"
            task.limitations.append("Arbitrary shell from chat is blocked by the V8 Operator contract.")
            task.plan.limitations.append("Use allowlisted validation presets instead of shell commands.")
        if action_type in {"git_commit", "git_push", "send_email", "send_sms", "browser_click", "desktop_click"}:
            task.limitations.append("This action is approval-gated and disabled by default.")
        return task

    def _action_type(self, request: OperatorTaskRequest) -> str:
        lower = f"{request.action_type} {request.prompt}".lower()
        if any(marker in lower for marker in ("shell", "powershell", "cmd.exe", "bash", "rm -rf", "curl | sh", "arbitrary command")):
            return "arbitrary_shell"
        if "git commit" in lower or "commit " in lower:
            return "git_commit"
        if "git push" in lower or "push " in lower:
            return "git_push"
        if "send email" in lower or "email " in lower:
            return "send_email"
        if "send sms" in lower or "text message" in lower:
            return "send_sms"
        if "browser click" in lower or "click browser" in lower:
            return "browser_click"
        if "delete" in lower:
            return "delete_file"
        if "write" in lower or "edit" in lower or "patch" in lower:
            return "write_file"
        if "git status" in lower:
            return "git_status"
        if "diff" in lower:
            return "git_diff"
        if "directory" in lower or "list" in lower:
            return "directory_listing"
        return "read_file"

    def _hash(self, action_type: str, target: str, prompt: str) -> str:
        return hashlib.sha256(f"{action_type}|{target}|{prompt}".encode("utf-8")).hexdigest()
