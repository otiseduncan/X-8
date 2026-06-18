from x8.contracts.base import Evidence, ResultEnvelope
from x8.contracts.managers import ManagerContext
from x8.contracts.receipts import Receipt
from x8.managers.audit_manager import audit_manager
from x8.managers.operator_manager import OperatorManager
from x8.managers.team_council_manager import TeamCouncilManager


class AssistantManager:
    name = "assistant"
    version = "0.1.0"

    def __init__(self, knowledge_root: str) -> None:
        self.team = TeamCouncilManager(knowledge_root)
        self.operator = OperatorManager()

    def respond(self, message: str) -> ResultEnvelope[dict[str, object]]:
        context = ManagerContext(user_message=message)
        team = self.team.execute(context)
        operator = self.operator.plan(context)
        receipt = audit_manager.record(
            Receipt(action="chat.respond", status="completed", summary="Structured assistant response generated.")
        )
        data = {
            "reply": "XV8 is ready to inspect, plan, preview, and request approval before mutation.",
            "team": team.data,
            "safe_development_loop": [step.model_dump() for step in operator.plan],
        }
        return ResultEnvelope(
            ok=True,
            status="implemented",
            data=data,
            message="Structured response created.",
            receipts=[receipt],
            evidence=[Evidence(source="runtime", summary="Chat manager executed in this request.", verified=True)],
        )
