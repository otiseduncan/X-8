from pydantic import BaseModel, Field

from x8.contracts.capability import CapabilityStatus


class ToolCallRequest(BaseModel):
    tool: str
    action: str
    args: dict[str, str] = Field(default_factory=dict)
    approved: bool = False


class ToolCallResult(BaseModel):
    tool: str
    status: CapabilityStatus
    output: str
    mutated: bool = False


class IntegrationStatus(BaseModel):
    name: str
    status: CapabilityStatus
    summary: str
    credential_required: bool = False
    approval_required: bool = True
