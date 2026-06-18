from enum import StrEnum

from pydantic import BaseModel


class CapabilityStatus(StrEnum):
    IMPLEMENTED = "implemented"
    DISABLED = "disabled"
    STUBBED = "stubbed"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


class Capability(BaseModel):
    name: str
    status: CapabilityStatus
    summary: str
    requires_approval: bool = False
    evidence: str = "declared_by_contract"
