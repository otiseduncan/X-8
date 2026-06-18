from x8.operator.contracts import RiskLevel, ToolSpec
from x8.operator.tools.base import OperatorTool


class DesktopClickTool(OperatorTool):
    spec = ToolSpec(action_type="desktop_click", risk_level=RiskLevel.REMOTE_CONTROL, requires_approval=True, allowed_targets=["visible_desktop"], limitations=["Desktop control disabled by default."])
