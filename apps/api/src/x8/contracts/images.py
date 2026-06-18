from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class ImageGenerationRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    model: str = "juggernaut"
    workflow: str = "text_to_image"
    seed: int | None = None
    steps: int = 30
    cfg: float = 7.0
    sampler: str = "euler"
    resolution: str = "1024x1024"
    approved: bool = False


class ImageGenerationResult(BaseModel):
    status: str
    reason: str
    image_generated: bool = False
    provider: str = "comfyui"
    model: str = "juggernaut"
    output_paths: list[str] = Field(default_factory=list)


class ImageGenerationReceipt(BaseModel):
    id: str = Field(default_factory=lambda: f"image_{uuid4().hex[:12]}")
    provider: str
    model: str
    status: str
    prompt_summary: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
