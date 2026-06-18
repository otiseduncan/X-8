from x8.adapters.integrations.comfyui_adapter import ComfyUIAdapter
from x8.contracts.images import ImageGenerationReceipt, ImageGenerationRequest, ImageGenerationResult


class ImageGenerationManager:
    name = "image_generation"
    version = "0.1.0"

    def __init__(self, base_url: str, model_dir: str, workflow_dir: str) -> None:
        self.comfy = ComfyUIAdapter(base_url, model_dir, workflow_dir)

    def status(self) -> dict[str, object]:
        status = self.comfy.status()
        status["juggernaut"] = self.comfy.juggernaut_status()
        status["models"] = self.comfy.models()
        status["workflows"] = self.comfy.workflows()
        return status

    def generate(self, request: ImageGenerationRequest) -> tuple[ImageGenerationResult, ImageGenerationReceipt]:
        model_status = self.comfy.juggernaut_status()
        if model_status["status"] == "model_missing":
            result = ImageGenerationResult(status="model_missing", reason="Juggernaut checkpoint was not found")
        elif not request.approved:
            result = ImageGenerationResult(status="pending_click", reason="Image generation requires click approval.", model=request.model)
        else:
            result = ImageGenerationResult(status="queued", reason="Generation request accepted by XV8; ComfyUI queue submission is not faked.", model=request.model)
        receipt = ImageGenerationReceipt(provider="comfyui", model=request.model, status=result.status, prompt_summary=request.prompt[:120])
        return result, receipt
