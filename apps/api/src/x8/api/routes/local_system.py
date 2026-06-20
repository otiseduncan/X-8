from fastapi import APIRouter, Request

from x8.adapters.integrations.local_system_adapter import LocalSystemAdapter, LocalSystemStatus
from x8.contracts.base import ResultEnvelope

router = APIRouter(prefix="/api/local-system", tags=["local_system"])


@router.get("/status", response_model=ResultEnvelope[LocalSystemStatus])
def status(request: Request) -> ResultEnvelope[LocalSystemStatus]:
    settings = request.app.state.settings
    data = LocalSystemAdapter(settings.workspace_root, settings.approved_project_roots).status()
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Local system status reported honestly.")
