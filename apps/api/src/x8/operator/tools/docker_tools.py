from x8.operator.contracts import RiskLevel, ToolSpec
from x8.operator.tools.base import OperatorTool


class DockerStatusTool(OperatorTool):
    spec = ToolSpec(action_type="docker_status", risk_level=RiskLevel.READ_ONLY, requires_approval=False, allowed_targets=["compose_project"])
