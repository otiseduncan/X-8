import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.chat import SessionDetail, SessionSummary
from x8.storage.postgres_store import PostgresStore

router = APIRouter(prefix="/api", tags=["sessions"])


def _decode_receipt(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["limitations"] = json.loads(data.pop("limitations_json", "[]"))
    data["metadata"] = json.loads(data.pop("metadata_json", "{}"))
    return data


def _decode_message(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["cards"] = json.loads(data.pop("cards_json", "[]"))
    return data


@router.get("/sessions", response_model=ResultEnvelope[list[SessionSummary]])
def list_sessions(request: Request) -> ResultEnvelope[list[SessionSummary]]:
    sessions = [SessionSummary(**row) for row in PostgresStore(request.app.state.settings.database_url).list_sessions()]
    return ResultEnvelope(ok=True, status="ok", data=sessions, message=f"{len(sessions)} sessions found.")


@router.get("/sessions/{session_id}", response_model=ResultEnvelope[SessionDetail])
def get_session(session_id: str, request: Request) -> ResultEnvelope[SessionDetail]:
    data = PostgresStore(request.app.state.settings.database_url).get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    session = data["session"]
    return ResultEnvelope(
        ok=True,
        status="ok",
        data=SessionDetail(
            session_id=session["session_id"],
            title=session["title"],
            messages=[_decode_message(row) for row in data["messages"]],
            receipts=[_decode_receipt(row) for row in data["receipts"]],
        ),
        message="Session loaded.",
    )
