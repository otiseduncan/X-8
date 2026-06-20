from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.chat_ide_manager import ChatIDEManager, IDECommandProposal, IDECommandResult, IDEPermission, IDERollbackProposal, IDESummary
from x8.managers.workspace_manager import FileRead

router = APIRouter(prefix="/api/ide", tags=["ide"])


class IDEPathRequest(BaseModel):
    path: str = "README.md"


class IDEPermissionRequest(BaseModel):
    action: str
    scope: str = "workspace"


class IDECommandRequest(BaseModel):
    command: str
    approved: bool = False


class IDERollbackRequest(BaseModel):
    action: str


def manager(request: Request) -> ChatIDEManager:
    settings = request.app.state.settings
    return ChatIDEManager(settings.workspace_root, settings.github_token, settings.github_owner, settings.github_default_visibility)


@router.get("/summary", response_model=ResultEnvelope[IDESummary])
def ide_summary(request: Request, selected_path: str = "README.md") -> ResultEnvelope[IDESummary]:
    data = manager(request).summary(selected_path)
    return ResultEnvelope(ok=True, status="ready", data=data, message="Chat IDE workspace summary loaded.", receipts=[Receipt(action="ide.summary", status="ready", summary="Workspace, Git, permissions, and activity loaded.")])


@router.post("/open-file", response_model=ResultEnvelope[FileRead])
def ide_open_file(payload: IDEPathRequest, request: Request) -> ResultEnvelope[FileRead]:
    try:
        data = manager(request).open_file(payload.path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResultEnvelope(ok=True, status="ready", data=data, message="IDE file opened read-only.", receipts=[Receipt(action="ide.open_file", status="ready", summary=f"Opened {payload.path} read-only.")])


@router.post("/permission", response_model=ResultEnvelope[IDEPermission])
def ide_permission(payload: IDEPermissionRequest, request: Request) -> ResultEnvelope[IDEPermission]:
    data = manager(request).permission(payload.action, payload.scope)
    return ResultEnvelope(ok=data.allowed and not data.blocked, status="blocked" if data.blocked else "approval_required" if data.approval_required else "allowed", data=data, message=data.reason, receipts=[Receipt(action=f"ide.permission.{payload.action}", status="blocked" if data.blocked else "allowed", summary=data.reason)])


@router.post("/command/propose", response_model=ResultEnvelope[IDECommandProposal])
def ide_command_propose(payload: IDECommandRequest, request: Request) -> ResultEnvelope[IDECommandProposal]:
    data = manager(request).propose_command(payload.command)
    return ResultEnvelope(ok=data.allowed and not data.blocked, status="blocked" if data.blocked else "proposed", data=data, message=data.reason, receipts=[Receipt(action="ide.command.propose", status="blocked" if data.blocked else "proposed", summary=data.reason)])


@router.post("/command/run", response_model=ResultEnvelope[IDECommandResult])
def ide_command_run(payload: IDECommandRequest, request: Request) -> ResultEnvelope[IDECommandResult]:
    data = manager(request).run_command(payload.command, payload.approved)
    return ResultEnvelope(ok=data.status == "passed", status=data.status, data=data, message=data.blocked_reason or f"Command {data.status}.", receipts=[Receipt(action="ide.command.run", status=data.status, summary=data.blocked_reason or f"Command {data.status}.", metadata={"command": data.command, "exit_code": data.exit_code})])


@router.get("/git/status", response_model=ResultEnvelope[dict[str, object]])
def ide_git_status(request: Request) -> ResultEnvelope[dict[str, object]]:
    data = manager(request).git_status()
    return ResultEnvelope(ok=True, status="ready", data=data, message="IDE Git status loaded.", receipts=[Receipt(action="ide.git_status", status="ready", summary="Git status loaded without mutation.")])


@router.post("/rollback/propose", response_model=ResultEnvelope[IDERollbackProposal])
def ide_rollback_propose(payload: IDERollbackRequest, request: Request) -> ResultEnvelope[IDERollbackProposal]:
    data = manager(request).rollback_proposal(payload.action)
    return ResultEnvelope(ok=data.allowed, status="approval_required" if data.approval_required else "ready", data=data, message=data.reason, receipts=[Receipt(action="ide.rollback.propose", status="approval_required" if data.approval_required else "ready", summary=data.reason)])
