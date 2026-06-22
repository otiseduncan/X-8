from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request

from x8.adapters.integrations.local_bridge_adapter import LocalBridgeAdapter, LocalBridgeStatus, PowerShellOpenResult
from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.project_registry_manager import ProjectRegistryManager

router = APIRouter(prefix="/api/local-bridge", tags=["local_bridge"])


class OpenProjectPowerShellRequest(BaseModel):
    project_id: str | None = None


class ProjectPowerShellOpenResult(PowerShellOpenResult):
    project_id: str
    project_name: str
    project_root: str
    terminal_path: str | None = None


def project_registry(request: Request) -> ProjectRegistryManager:
    settings = request.app.state.settings
    return ProjectRegistryManager(
        settings.workspace_root,
        settings.approved_project_roots,
        workspace_host_root=settings.workspace_host_root,
        projects_host_root=settings.projects_host_root,
    )


@router.get("/status", response_model=ResultEnvelope[LocalBridgeStatus])
def status(request: Request) -> ResultEnvelope[LocalBridgeStatus]:
    settings = request.app.state.settings
    data = LocalBridgeAdapter(settings.local_bridge_url, settings.local_bridge_token, settings.approved_project_roots).status()
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Local bridge status reported honestly.")


@router.post("/open-powershell", response_model=ResultEnvelope[ProjectPowerShellOpenResult])
def open_powershell(payload: OpenProjectPowerShellRequest, request: Request) -> ResultEnvelope[ProjectPowerShellOpenResult]:
    settings = request.app.state.settings
    try:
        project = project_registry(request).get_project(payload.project_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    terminal_path = project.terminal_path
    if not terminal_path:
        command = "Configure X8_WORKSPACE_HOST_ROOT for X-8 or X8_PROJECTS_HOST_ROOT for mounted projects."
        data = ProjectPowerShellOpenResult(
            project_id=project.id,
            project_name=project.name,
            project_root=project.root,
            terminal_path=None,
            requested_path=project.root,
            command=command,
            launched=False,
            supported=False,
            message="PowerShell host path is not configured for this project.",
            fallback_reason="The API knows the container path, but opening Windows PowerShell requires the matching Windows host path.",
        )
        receipt = Receipt(action="local_bridge.open_powershell", status="blocked", summary=data.message)
        return ResultEnvelope(ok=True, status="blocked", data=data, message=data.message, receipts=[receipt])

    bridge_result = LocalBridgeAdapter(settings.local_bridge_url, settings.local_bridge_token, settings.approved_project_roots).open_powershell(terminal_path)
    data = ProjectPowerShellOpenResult(
        project_id=project.id,
        project_name=project.name,
        project_root=project.root,
        terminal_path=terminal_path,
        **bridge_result.model_dump(),
    )
    receipt_status = "completed" if data.launched else "blocked"
    receipt = Receipt(action="local_bridge.open_powershell", status=receipt_status, summary=data.message)
    return ResultEnvelope(ok=True, status=receipt_status, data=data, message=data.message, receipts=[receipt])
