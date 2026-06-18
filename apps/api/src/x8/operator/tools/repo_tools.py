from x8.operator.contracts import RiskLevel, ToolSpec
from x8.operator.tools.base import OperatorTool


class RepoStatusTool(OperatorTool):
    spec = ToolSpec(action_type="git_status", risk_level=RiskLevel.READ_ONLY, requires_approval=False, allowed_targets=["workspace"])
