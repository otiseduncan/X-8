from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class AvatarAsset(BaseModel):
    path: str
    asset_type: str
    imported: bool = False
    id: str = ""
    label: str = ""
    states: list[str] = Field(default_factory=list)
    loop: bool = True
    muted: bool = True


class AvatarManifest(BaseModel):
    status: str
    reason: str
    fallback_available: bool
    default_asset: str | None = None
    assets: list[AvatarAsset] = Field(default_factory=list)


class AvatarState(BaseModel):
    active_asset: str | None
    expression: str = "neutral"
    speech_state: str = "idle"


class AvatarImportReceipt(BaseModel):
    id: str = Field(default_factory=lambda: f"avatar_{uuid4().hex[:12]}")
    status: str
    assets_imported: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AvatarStatus(BaseModel):
    status: str
    manifest_found: bool
    asset_count: int
    video_asset_count: int
    active_state: str = "idle"
    states_available: list[str] = Field(default_factory=list)
    fallback_available: bool
    limitations: list[str] = Field(default_factory=list)
