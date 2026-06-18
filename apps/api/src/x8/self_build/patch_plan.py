from x8.self_build.contracts import SelfBuildPlan, SelfBuildTask
from x8.self_build.planner import BuildTaskPlanner


class PatchPlanManager:
    def __init__(self) -> None:
        self.planner = BuildTaskPlanner()

    def create(self, task: SelfBuildTask) -> SelfBuildPlan:
        return self.planner.create_plan(task)
