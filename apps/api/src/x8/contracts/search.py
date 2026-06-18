from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceCitationContract(BaseModel):
    title: str
    url: str
    snippet: str = ""
    freshness: str = "unknown"


class SearchResultContract(BaseModel):
    query: str
    provider: str
    status: str
    reason: str = ""
    search_ran: bool = False
    results: list[SourceCitationContract] = Field(default_factory=list)


class ResearchReceipt(BaseModel):
    id: str = Field(default_factory=lambda: f"research_{uuid4().hex[:12]}")
    provider: str
    query: str
    status: str
    result_count: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
