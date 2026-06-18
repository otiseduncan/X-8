from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.safe_repo_writer_manager import PatchProposal, SafeRepoWriterManager
from x8.managers.workspace_manager import FileEntry, FileRead, WorkspaceManager

router = APIRouter(prefix="/api", tags=["workspace"])


class SearchRequest(BaseModel):
    query: str


class ReadRequest(BaseModel):
    path: str


class UpdateRequest(BaseModel):
    path: str
    proposed_content: str
    approved: bool = False


def workspace_manager(request: Request) -> WorkspaceManager:
    return WorkspaceManager(request.app.state.settings.workspace_root)


@router.get("/workspace/files", response_model=ResultEnvelope[list[FileEntry]])
def files(request: Request) -> ResultEnvelope[list[FileEntry]]:
    receipt = Receipt(action="workspace.list_files", status="completed", summary="File tree inspected without approval.")
    return ResultEnvelope(ok=True, status="implemented", data=workspace_manager(request).list_files(), message="Workspace files listed.", receipts=[receipt])


@router.post("/workspace/search", response_model=ResultEnvelope[list[FileEntry]])
def search(payload: SearchRequest, request: Request) -> ResultEnvelope[list[FileEntry]]:
    receipt = Receipt(action="workspace.search", status="completed", summary="Workspace search completed without approval.")
    return ResultEnvelope(ok=True, status="implemented", data=workspace_manager(request).search(payload.query), message="Workspace search completed.", receipts=[receipt])


@router.post("/workspace/read", response_model=ResultEnvelope[FileRead])
def read(payload: ReadRequest, request: Request) -> ResultEnvelope[FileRead]:
    try:
        data = workspace_manager(request).read_file(payload.path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    receipt = Receipt(action="workspace.read_file", status="completed", summary=f"Opened {payload.path} without approval.")
    return ResultEnvelope(ok=True, status="implemented", data=data, message="File read completed.", receipts=[receipt])


@router.post("/repo/propose-update", response_model=ResultEnvelope[PatchProposal])
def propose_update(payload: UpdateRequest, request: Request) -> ResultEnvelope[PatchProposal]:
    proposal = SafeRepoWriterManager(workspace_manager(request)).propose_update(payload.path, payload.proposed_content)
    return ResultEnvelope(ok=True, status="proposed", data=proposal, message="Patch proposal created.", receipts=[proposal.receipt])


@router.post("/repo/apply-update", response_model=ResultEnvelope[PatchProposal])
def apply_update(payload: UpdateRequest, request: Request) -> ResultEnvelope[PatchProposal]:
    proposal = SafeRepoWriterManager(workspace_manager(request)).apply_update(payload.path, payload.proposed_content, payload.approved)
    return ResultEnvelope(ok=True, status=proposal.receipt.status, data=proposal, message=proposal.receipt.summary, receipts=[proposal.receipt])
