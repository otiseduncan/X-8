from pydantic import BaseModel
from fastapi import APIRouter

from x8.contracts.base import ResultEnvelope
from x8.managers.artifact_manager import ArtifactManager, ArtifactPreview

router = APIRouter(prefix="/api", tags=["artifacts"])


class ArtifactRequest(BaseModel):
    title: str = "Untitled preview"
    prompt: str


@router.post("/artifacts/preview", response_model=ResultEnvelope[ArtifactPreview])
def artifact_preview(payload: ArtifactRequest) -> ResultEnvelope[ArtifactPreview]:
    preview = ArtifactManager().create_html_preview(payload.title, payload.prompt)
    return ResultEnvelope(ok=True, status="implemented", data=preview, message="Preview created without repo mutation.", receipts=[preview.receipt])
