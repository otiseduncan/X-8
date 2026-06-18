from typing import Any, Protocol

from pydantic import BaseModel, Field

from x8.contracts.capability import Capability
from x8.contracts.receipts import Receipt


class PlanStep(BaseModel):
    title: str
    status: str = "pending"
    risk: str = "low"


class TeamSeat(BaseModel):
    name: str
    responsibility: str
    boundaries: list[str]
    reviews: list[str]
    catches: list[str]
    output_style: str


class ManagerContext(BaseModel):
    user_message: str = ""
    intent: str = "general"
    approved_actions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManagerResponse(BaseModel):
    manager: str
    message: str
    plan: list[PlanStep] = Field(default_factory=list)
    receipts: list[Receipt] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class ManagerProtocol(Protocol):
    name: str
    version: str

    def capabilities(self) -> list[Capability]:
        ...

    def plan(self, context: ManagerContext) -> ManagerResponse:
        ...

    def execute(self, context: ManagerContext) -> ManagerResponse:
        ...
