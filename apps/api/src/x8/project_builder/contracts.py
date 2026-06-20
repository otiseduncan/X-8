from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class ProjectBuilderStatus(StrEnum):
    PREVIEW = "preview"
    WRITTEN = "written"
    BLOCKED = "blocked"


class ProjectBuilderRequest(BaseModel):
    prompt: str
    project_name: str = "x8-generated-project"
    approved: bool = False
    manifest_hash: str = ""
    sandbox_path: str = ""


class GeneratedProjectFile(BaseModel):
    path: str
    content: str
    sha256: str
    size_bytes: int


class GeneratedProjectPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: _id("pbplan"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    project_name: str
    project_slug: str
    sandbox_root: str
    output_path: str
    manifest_hash: str
    files: list[GeneratedProjectFile]
    safe_actions: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)
    status: ProjectBuilderStatus = ProjectBuilderStatus.PREVIEW


class ProjectBuilderResult(BaseModel):
    request_id: str = Field(default_factory=lambda: _id("pbreq"))
    status: ProjectBuilderStatus
    message: str
    plan: GeneratedProjectPlan
    wrote_files: bool = False
    written_files: list[str] = Field(default_factory=list)
    receipt: dict[str, object] = Field(default_factory=dict)
