from pathlib import Path

import httpx


class ComfyUIAdapter:
    name = "ComfyUI"
    version = "0.1.0"

    def __init__(self, base_url: str, model_dir: str, workflow_dir: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_dir = Path(model_dir)
        self.workflow_dir = Path(workflow_dir)

    def status(self) -> dict[str, object]:
        try:
            response = httpx.get(f"{self.base_url}/system_stats", timeout=3)
            return {"status": "available", "reachable": response.status_code < 500, "base_url": self.base_url}
        except Exception as exc:
            return {"status": "unavailable", "reachable": False, "reason": "ComfyUI service is not reachable", "error": str(exc)}

    def models(self) -> list[str]:
        if not self.model_dir.exists():
            return []
        patterns = ["*.safetensors", "*.ckpt"]
        found: list[str] = []
        for pattern in patterns:
            found.extend(path.name for path in self.model_dir.glob(pattern))
        return sorted(found)

    def workflows(self) -> list[str]:
        if not self.workflow_dir.exists():
            return []
        return sorted(path.name for path in self.workflow_dir.glob("*.json"))

    def juggernaut_status(self) -> dict[str, object]:
        matches = [name for name in self.models() if name.lower().startswith("juggernaut")]
        if not matches:
            return {"status": "model_missing", "reason": "Juggernaut checkpoint was not found", "image_generated": False}
        return {"status": "available", "model": matches[0], "image_generated": False}
