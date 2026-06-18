from fastapi import APIRouter

from x8.adapters.integrations.catalog import integration_catalog
from x8.contracts.base import ResultEnvelope
from x8.contracts.integrations import IntegrationStatus

router = APIRouter(prefix="/api", tags=["integrations"])


@router.get("/integrations", response_model=ResultEnvelope[list[IntegrationStatus]])
def integrations() -> ResultEnvelope[list[IntegrationStatus]]:
    data = [adapter.integration_status() for adapter in integration_catalog()]
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Integration statuses listed.")
