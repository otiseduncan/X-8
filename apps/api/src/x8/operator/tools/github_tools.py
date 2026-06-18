from x8.operator.contracts import RiskLevel, ToolSpec
from x8.operator.tools.base import OperatorTool


class GitHubPushTool(OperatorTool):
    spec = ToolSpec(action_type="git_push", risk_level=RiskLevel.EXTERNAL_SEND, requires_approval=True, allowed_targets=["configured_repo"])
