from pydantic import BaseModel
from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.contracts.search import SearchResultContract
from x8.managers.web_search_manager import WebSearchManager

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str


def manager(request: Request) -> WebSearchManager:
    settings = request.app.state.settings
    return WebSearchManager(settings.web_search_provider, settings.searxng_base_url)


@router.get("/status", response_model=ResultEnvelope[dict[str, object]])
def status(request: Request) -> ResultEnvelope[dict[str, object]]:
    data = manager(request).provider_status()
    return ResultEnvelope(ok=True, status=str(data.get("status", "unknown")), data=data, message=str(data.get("reason", "Provider status checked.")))


@router.post("/query", response_model=ResultEnvelope[SearchResultContract])
def query(payload: SearchRequest, request: Request) -> ResultEnvelope[SearchResultContract]:
    result, receipt = manager(request).search(payload.query)
    common_receipt = Receipt(action="search.query", status=receipt.status, summary=f"{receipt.result_count} search results from {receipt.provider}.", metadata=receipt.model_dump())
    return ResultEnvelope(ok=result.search_ran, status=result.status, data=result, message=result.reason or "Search completed.", receipts=[common_receipt])
