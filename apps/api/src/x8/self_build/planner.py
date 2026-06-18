from x8.self_build.contracts import SelfBuildPlan, SelfBuildPlanStep, SelfBuildTask


class BuildTaskPlanner:
    def create_plan(self, task: SelfBuildTask) -> SelfBuildPlan:
        targets = task.context.files_read if task.context else ["README.md"]
        tests = task.required_tests or ["architecture_guard"]
        return SelfBuildPlan(
            status="created",
            summary=f"Create a guarded patch proposal for: {task.goal}",
            target_files=targets,
            modified_files=targets,
            risk_level=task.risk_level,
            approval_required=True,
            tests_to_run=tests,
            rollback_plan="Keep before-content hashes and write backups before apply.",
            known_limitations=["Patch generation is deterministic scaffolded output until model-backed patching is enabled."],
            steps=[
                SelfBuildPlanStep(title="Inspect repo context", summary="Read allowed project files only.", status="completed"),
                SelfBuildPlanStep(title="Create diff proposal", summary="Generate diff without writing files.", status="pending"),
                SelfBuildPlanStep(title="Request popup approval", summary="Apply requires exact patch hash approval.", status="pending"),
                SelfBuildPlanStep(title="Run validation preset", summary=", ".join(tests), status="pending"),
            ],
        )
