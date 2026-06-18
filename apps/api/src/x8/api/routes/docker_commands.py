from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from x8.contracts.base import ResultEnvelope
from x8.managers.docker_command_preset_manager import DockerCommandPresetManager, DockerCommandResult

router = APIRouter(prefix="/api/docker", tags=["docker"])


class PresetRequest(BaseModel):
    preset_name: str
    approved: bool = False


@router.get("/presets", response_model=ResultEnvelope[list[str]])
def presets() -> ResultEnvelope[list[str]]:
    return ResultEnvelope(ok=True, status="implemented", data=DockerCommandPresetManager().presets(), message="Docker presets listed.")


@router.get("/preset-definitions", response_model=ResultEnvelope[list[dict[str, object]]])
def preset_definitions() -> ResultEnvelope[list[dict[str, object]]]:
    data = [preset.model_dump() for preset in DockerCommandPresetManager().preset_defs()]
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Docker preset definitions listed.")


@router.post("/run-preset", response_model=ResultEnvelope[DockerCommandResult])
def run_preset(payload: PresetRequest) -> ResultEnvelope[DockerCommandResult]:
    manager = DockerCommandPresetManager()
    if payload.preset_name not in manager.presets():
        raise HTTPException(status_code=400, detail="Unknown Docker command preset.")
    result = manager.run_preset(payload.preset_name, payload.approved)
    return ResultEnvelope(ok=result.status == "passed", status=result.status, data=result, message="Docker preset completed with real execution status.")
