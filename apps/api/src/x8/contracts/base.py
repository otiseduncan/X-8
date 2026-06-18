from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from x8.contracts.receipts import Receipt

T = TypeVar("T")


class Evidence(BaseModel):
    source: str
    summary: str
    verified: bool = False


class ResultEnvelope(BaseModel, Generic[T]):
    ok: bool
    status: str
    data: T | None = None
    message: str
    receipts: list[Receipt] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
