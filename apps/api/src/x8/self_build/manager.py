from pathlib import Path

from x8.self_build.audit import SelfBuildAuditManager
from x8.self_build.contracts import PatchApplyRequest, SelfBuildRequest, SelfBuildTask, SelfBuildValidationReport
from x8.self_build.patch_applier import SafePatchApplier
from x8.self_build.patch_plan import PatchPlanManager
from x8.self_build.patch_proposal import PatchProposalManager
from x8.self_build.prompt_ingestor import BuildPromptIngestor
from x8.self_build.receipts import SelfBuildReceiptManager
from x8.self_build.repo_context import RepoContextReader
from x8.self_build.validation import PatchValidationManager


class SelfBuildManager:
    def __init__(self, workspace_root: str = "/workspace") -> None:
        self.reader = RepoContextReader(workspace_root)
        self.ingestor = BuildPromptIngestor()
        self.plans = PatchPlanManager()
        self.proposals = PatchProposalManager(self.reader)
        self.validation = PatchValidationManager(self.reader)
        self.applier = SafePatchApplier(self.reader, str(Path(workspace_root) / "runtime" / "self-build-backups"))
        self.receipts = SelfBuildReceiptManager()
        self.audit = SelfBuildAuditManager()
        self.tasks: dict[str, SelfBuildTask] = {}
        self.approvals: dict[str, str] = {}
        self.latest_task_id: str = ""

    def detect(self, prompt: str) -> bool:
        return self.ingestor.is_self_build_prompt(prompt)

    def classify_intent(self, prompt: str) -> str:
        return self.ingestor.classify_intent(prompt)

    def create_task(self, request: SelfBuildRequest) -> SelfBuildTask:
        extracted = self.ingestor.extract(request.user_prompt)
        request.allowed_paths = request.allowed_paths or self.reader.allowed_paths()
        request.blocked_paths = request.blocked_paths or self.reader.blocked_paths()
        request.test_presets = request.test_presets or list(extracted["required_tests"] or ["architecture_guard"])
        preset_validation = self.validation.validate_presets(request.test_presets)
        context = self.reader.snapshot(extracted["files_to_inspect"])
        task = SelfBuildTask(
            request=request,
            goal=str(extracted["goal"]),
            task_type=str(extracted["task_type"]),
            constraints=list(extracted["constraints"]),
            blocked_actions=list(extracted["blocked_actions"]),
            required_tests=request.test_presets,
            completion_rule=str(extracted["completion_rule"]),
            commit_instruction=str(extracted["commit_instruction"]),
            risk_level=str(extracted["risk_level"]),
            context=context,
            status="planned",
        )
        task.plan = self.plans.create(task)
        task.proposal = self.proposals.create(task, task.plan)
        task.receipts.extend(
            [
                self.receipts.create("self_build_prompt_ingested", "completed", request.request_id, task.task_id),
                self.receipts.create("repo_context_read", "completed", request.request_id, task.task_id, files_read=context.files_read),
                self.receipts.create("patch_plan_created", "completed", request.request_id, task.task_id),
                self.receipts.create("patch_proposal_created", task.proposal.status, request.request_id, task.task_id, task.proposal.patch_id, limitations=preset_validation.reasons),
            ]
        )
        if task.proposal.validation.passed and request.approval_required:
            approval_id = f"sbappr_{task.proposal.patch_hash[:12]}"
            task.proposal.approval_id = approval_id
            self.approvals[approval_id] = task.proposal.patch_hash
            task.receipts.append(self.receipts.create("patch_approval_requested", "pending", request.request_id, task.task_id, task.proposal.patch_id, approval_id=approval_id))
        self.tasks[task.task_id] = task
        self.latest_task_id = task.task_id
        return task

    def get_task(self, task_id: str) -> SelfBuildTask | None:
        return self.tasks.get(task_id)

    def latest_task(self) -> SelfBuildTask | None:
        if self.latest_task_id:
            return self.tasks.get(self.latest_task_id)
        if not self.tasks:
            return None
        return list(self.tasks.values())[-1]

    def proposal_detail(self, task: SelfBuildTask) -> dict[str, object]:
        proposal = task.proposal
        if proposal is None:
            return {}
        return {
            "task_id": task.task_id,
            "patch_id": proposal.patch_id,
            "approval_id": proposal.approval_id,
            "patch_hash": proposal.patch_hash,
            "files_changed_count": len(proposal.changes),
            "changed_file_paths": [change.file_path for change in proposal.changes],
            "changes": [
                {
                    "file_path": change.file_path,
                    "before_hash": change.before_hash,
                    "after_hash": change.after_hash,
                    "unified_diff": change.unified_diff,
                }
                for change in proposal.changes
            ],
            "validation_status": proposal.validation.status,
            "validation_reasons": proposal.validation.reasons,
            "task_type": task.plan.task_type if task.plan else task.task_type,
            "tests_to_run": task.plan.tests_to_run if task.plan else task.required_tests,
            "risk_level": task.plan.risk_level if task.plan else task.risk_level,
            "rollback_plan": task.plan.rollback_plan if task.plan else "",
            "apply_safe": bool(proposal.validation.passed and proposal.approval_id and proposal.patch_hash),
            "message": "No files changed. Approval required before apply.",
        }

    def latest_proposal_detail(self) -> dict[str, object] | None:
        task = self.latest_task()
        if task is None or task.proposal is None:
            return None
        return self.proposal_detail(task)

    def latest_validation_report(self) -> SelfBuildValidationReport | None:
        task = self.latest_task()
        if task is None or not task.validation_reports:
            return None
        return task.validation_reports[-1]

    def apply_patch(self, task_id: str, request: PatchApplyRequest):
        task = self.tasks[task_id]
        proposal = task.proposal
        if proposal is None:
            raise ValueError("Task has no patch proposal.")
        approval_hash = self.approvals.get(request.approval_id, "")
        result = self.applier.apply(proposal, request, approval_hash)
        task.receipts.append(
            self.receipts.create(
                "patch_applied" if result.applied else "patch_apply_failed",
                result.status,
                task.request.request_id,
                task.task_id,
                proposal.patch_id,
                approval_id=request.approval_id,
                files_changed=result.changed_files,
                limitations=[] if result.applied else [result.reason],
                patch_hash=proposal.patch_hash,
                validation_passed=result.validation_passed,
                applied=result.applied,
                reverted=result.reverted,
                failure_reason="" if result.applied else result.reason,
            )
        )
        return result

    def validate_task(self, task_id: str) -> SelfBuildValidationReport:
        task = self.tasks[task_id]
        proposal = task.proposal
        patch_id = proposal.patch_id if proposal else ""
        patch_hash = proposal.patch_hash if proposal else ""
        runs = self.validation.run_presets(task.required_tests)
        passed = bool(runs) and all(item.passed for item in runs)
        failure = "" if passed else "One or more self-build validation presets failed or did not run."
        report = SelfBuildValidationReport(
            task_id=task.task_id,
            patch_id=patch_id,
            patch_hash=patch_hash,
            applied=self._last_apply_state(task)[0],
            reverted=self._last_apply_state(task)[1],
            validation_passed=passed,
            validation_runs=runs,
            failure_reason=failure,
            status="passed" if passed else "failed",
        )
        task.validation_reports.append(report)
        task.receipts.append(
            self.receipts.create(
                "self_build_validation",
                report.status,
                task.request.request_id,
                task.task_id,
                patch_id,
                tests_run=[item.preset for item in runs if item.ran],
                patch_hash=patch_hash,
                validation_passed=passed,
                failure_reason=failure,
            )
        )
        return report

    def _last_apply_state(self, task: SelfBuildTask) -> tuple[bool, bool]:
        for receipt in reversed(task.receipts):
            if receipt.action_type in {"patch_applied", "patch_apply_failed"}:
                return receipt.applied, receipt.reverted
        return False, False

    def trust_status(self) -> dict[str, object]:
        return {
            "approval_required": True,
            "approval_hash_required": True,
            "allowed_paths": self.reader.allowed_paths(),
            "blocked_paths": self.reader.blocked_paths(),
            "validation_presets": sorted(self.validation.preset_commands(["architecture_guard", "api_tests", "web_tests", "e2e_tests", "web_build", "compose_config"]).keys()),
            "writes_without_approval": False,
            "commit_allowed_by_default": False,
            "push_allowed_by_default": False,
            "status": "ready",
        }
