from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.project_registry_manager import ProjectRegistryManager, ProjectRoot
from x8.managers.safe_repo_writer_manager import PatchProposal, SafeRepoWriterManager
from x8.managers.workspace_manager import FileEntry, FileRead, WorkspaceManager

router = APIRouter(prefix="/api", tags=["workspace"])


class ProjectScopedRequest(BaseModel):
    project_id: str | None = None


class SearchRequest(ProjectScopedRequest):
    query: str


class ReadRequest(ProjectScopedRequest):
    path: str


class UpdateRequest(ProjectScopedRequest):
    path: str
    proposed_content: str
    approved: bool = False


def project_registry(request: Request) -> ProjectRegistryManager:
    settings = request.app.state.settings
    return ProjectRegistryManager(settings.workspace_root, settings.approved_project_roots)


def workspace_manager(request: Request, project_id: str | None = None) -> WorkspaceManager:
    project = project_registry(request).get_project(project_id)
    return WorkspaceManager(project.root)


@router.get("/projects", response_model=ResultEnvelope[list[ProjectRoot]])
def projects(request: Request) -> ResultEnvelope[list[ProjectRoot]]:
    data = project_registry(request).list_projects()
    receipt = Receipt(action="projects.list", status="completed", summary="Approved project registry inspected without mutation.")
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Approved projects listed.", receipts=[receipt])


@router.get("/workspace/files", response_model=ResultEnvelope[list[FileEntry]])
def files(request: Request, project_id: str | None = None) -> ResultEnvelope[list[FileEntry]]:
    try:
        manager = workspace_manager(request, project_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    receipt = Receipt(action="workspace.list_files", status="completed", summary="File tree inspected for selected project without approval.")
    return ResultEnvelope(ok=True, status="implemented", data=manager.list_files(), message="Workspace files listed.", receipts=[receipt])


@router.post("/workspace/search", response_model=ResultEnvelope[list[FileEntry]])
def search(payload: SearchRequest, request: Request) -> ResultEnvelope[list[FileEntry]]:
    try:
        manager = workspace_manager(request, payload.project_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    receipt = Receipt(action="workspace.search", status="completed", summary="Workspace search completed for selected project without approval.")
    return ResultEnvelope(ok=True, status="implemented", data=manager.search(payload.query), message="Workspace search completed.", receipts=[receipt])


@router.post("/workspace/read", response_model=ResultEnvelope[FileRead])
def read(payload: ReadRequest, request: Request) -> ResultEnvelope[FileRead]:
    try:
        data = workspace_manager(request, payload.project_id).read_file(payload.path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    receipt = Receipt(action="workspace.read_file", status="completed", summary=f"Opened {payload.path} from selected project without approval.")
    return ResultEnvelope(ok=True, status="implemented", data=data, message="File read completed.", receipts=[receipt])


@router.post("/repo/propose-update", response_model=ResultEnvelope[PatchProposal])
def propose_update(payload: UpdateRequest, request: Request) -> ResultEnvelope[PatchProposal]:
    try:
        proposal = SafeRepoWriterManager(workspace_manager(request, payload.project_id)).propose_update(payload.path, payload.proposed_content)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResultEnvelope(ok=True, status="proposed", data=proposal, message="Patch proposal created.", receipts=[proposal.receipt])


@router.post("/repo/apply-update", response_model=ResultEnvelope[PatchProposal])
def apply_update(payload: UpdateRequest, request: Request) -> ResultEnvelope[PatchProposal]:
    try:
        proposal = SafeRepoWriterManager(workspace_manager(request, payload.project_id)).apply_update(payload.path, payload.proposed_content, payload.approved)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResultEnvelope(ok=True, status=proposal.receipt.status, data=proposal, message=proposal.receipt.summary, receipts=[proposal.receipt])
