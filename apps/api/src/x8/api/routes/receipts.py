import json
from typing import Any

from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.storage.postgres_store import PostgresStore

router = APIRouter(prefix="/api", tags=["receipts"])


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["limitations"] = json.loads(data.pop("limitations_json", "[]"))
    data["metadata"] = json.loads(data.pop("metadata_json", "{}"))
    return data


@router.get("/receipts", response_model=ResultEnvelope[list[dict[str, Any]]])
def list_receipts(request: Request) -> ResultEnvelope[list[dict[str, Any]]]:
    receipts = [_decode(row) for row in PostgresStore(request.app.state.settings.database_url).list_receipts()]
    return ResultEnvelope(ok=True, status="ok", data=receipts, message=f"{len(receipts)} receipts found.")
