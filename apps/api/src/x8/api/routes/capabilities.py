from fastapi import APIRouter

from x8.contracts.base import ResultEnvelope
from x8.contracts.capability import Capability
from x8.services.capability_service import list_capabilities

router = APIRouter(prefix="/api", tags=["capabilities"])


@router.get("/capabilities", response_model=ResultEnvelope[list[Capability]])
def capabilities() -> ResultEnvelope[list[Capability]]:
    return ResultEnvelope(ok=True, status="implemented", data=list_capabilities(), message="Capabilities listed.")
