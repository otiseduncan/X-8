from x8.operator.contracts import RiskLevel, ToolSpec
from x8.operator.tools.base import OperatorTool


class SendEmailTool(OperatorTool):
    spec = ToolSpec(action_type="send_email", risk_level=RiskLevel.EXTERNAL_SEND, requires_approval=True, allowed_targets=["previewed_recipient"], limitations=["External sends disabled by default."])
