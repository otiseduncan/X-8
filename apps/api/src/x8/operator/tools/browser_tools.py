from x8.operator.contracts import RiskLevel, ToolSpec
from x8.operator.tools.base import OperatorTool


class BrowserClickTool(OperatorTool):
    spec = ToolSpec(action_type="browser_click", risk_level=RiskLevel.REMOTE_CONTROL, requires_approval=True, allowed_targets=["visible_browser"], limitations=["Remote control disabled by default."])
