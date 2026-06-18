from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.managers import TeamSeat
from x8.managers.team_council_manager import TeamCouncilManager

router = APIRouter(prefix="/api", tags=["team"])


@router.get("/team/seats", response_model=ResultEnvelope[list[TeamSeat]])
def team_seats(request: Request) -> ResultEnvelope[list[TeamSeat]]:
    manager = TeamCouncilManager(request.app.state.settings.knowledge_root)
    return ResultEnvelope(ok=True, status="implemented", data=manager.seats(), message="Team seats loaded.")
