from x8.self_build.contracts import SelfBuildPlan, SelfBuildPlanStep, SelfBuildTask


class BuildTaskPlanner:
    def create_plan(self, task: SelfBuildTask) -> SelfBuildPlan:
        task_type = self._task_type(task)
        targets = self._targets(task_type, task)
        tests = task.required_tests or ["architecture_guard"]
        limitations = [] if targets else ["Self-build needs a bounded safe target path. Ask for a docs-only, smoke-proof, small config/comment, or test-fixture proposal inside the workspace."]
        return SelfBuildPlan(
            status="created",
            task_type=task_type,
            summary=f"Create a guarded patch proposal for: {task.goal}",
            target_files=targets,
            modified_files=targets,
            risk_level=task.risk_level,
            approval_required=True,
            tests_to_run=tests,
            rollback_plan="Keep before-content hashes and write backups before apply.",
            known_limitations=limitations,
            steps=[
                SelfBuildPlanStep(title="Inspect repo context", summary="Read allowed project files only.", status="completed"),
                SelfBuildPlanStep(title="Create diff proposal", summary="Generate diff without writing files.", status="pending"),
                SelfBuildPlanStep(title="Request popup approval", summary="Apply requires exact patch hash approval.", status="pending"),
                SelfBuildPlanStep(title="Run validation preset", summary=", ".join(tests), status="pending"),
            ],
        )

    def _task_type(self, task: SelfBuildTask) -> str:
        return task.task_type or "unknown_safe"

    def _targets(self, task_type: str, task: SelfBuildTask) -> list[str]:
        read_files = task.context.files_read if task.context else []
        if task_type in {"ui_feature", "api_feature", "test_only", "docs_only", "config_change", "repair_patch", "project_builder_feature", "smoke_proof"}:
            return read_files
        return []
