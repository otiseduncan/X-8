import json
from pathlib import Path

from x8.contracts.capability import Capability, CapabilityStatus
from x8.contracts.managers import ManagerContext, ManagerResponse, PlanStep, TeamSeat


class TeamCouncilManager:
    name = "team_council"
    version = "0.1.0"

    def __init__(self, knowledge_root: str = "/app/knowledge") -> None:
        self.knowledge_root = Path(knowledge_root)

    def capabilities(self) -> list[Capability]:
        return [Capability(name="team_council", status=CapabilityStatus.IMPLEMENTED, summary="Loads seeded senior team seats.")]

    def seats(self) -> list[TeamSeat]:
        path = self.knowledge_root / "team" / "seats.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return [TeamSeat(**item) for item in data["seats"]]

    def plan(self, context: ManagerContext) -> ManagerResponse:
        seats = self.seats()
        steps = [PlanStep(title=f"Consult {seat.name}", risk="low") for seat in seats[:4]]
        return ManagerResponse(manager=self.name, message="Team council loaded.", plan=steps)

    def execute(self, context: ManagerContext) -> ManagerResponse:
        names = [seat.name for seat in self.seats()]
        return ManagerResponse(manager=self.name, message="Relevant team seats are available.", data={"seats": names})
