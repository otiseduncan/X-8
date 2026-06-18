from fastapi import APIRouter, Request

from x8.adapters.integrations.local_bridge_adapter import LocalBridgeAdapter, LocalBridgeStatus
from x8.contracts.base import ResultEnvelope

router = APIRouter(prefix="/api/local-bridge", tags=["local_bridge"])


@router.get("/status", response_model=ResultEnvelope[LocalBridgeStatus])
def status(request: Request) -> ResultEnvelope[LocalBridgeStatus]:
    settings = request.app.state.settings
    data = LocalBridgeAdapter(settings.local_bridge_url, settings.local_bridge_token, settings.approved_project_roots).status()
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Local bridge status reported honestly.")
