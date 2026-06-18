from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.images import ImageGenerationRequest, ImageGenerationResult
from x8.contracts.receipts import Receipt
from x8.managers.image_generation_manager import ImageGenerationManager

router = APIRouter(prefix="/api/images", tags=["images"])


def manager(request: Request) -> ImageGenerationManager:
    settings = request.app.state.settings
    return ImageGenerationManager(settings.comfyui_base_url, settings.comfyui_model_dir, settings.comfyui_workflow_dir)


@router.get("/status", response_model=ResultEnvelope[dict[str, object]])
def status(request: Request) -> ResultEnvelope[dict[str, object]]:
    data = manager(request).status()
    return ResultEnvelope(ok=True, status=str(data.get("status", "unknown")), data=data, message="ComfyUI status checked.")


@router.post("/generate", response_model=ResultEnvelope[ImageGenerationResult])
def generate(payload: ImageGenerationRequest, request: Request) -> ResultEnvelope[ImageGenerationResult]:
    result, receipt = manager(request).generate(payload)
    common_receipt = Receipt(action="images.generate", status=receipt.status, summary=receipt.prompt_summary, metadata=receipt.model_dump())
    return ResultEnvelope(ok=result.image_generated, status=result.status, data=result, message=result.reason, receipts=[common_receipt])
