from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.project_builder.contracts import ProjectBuilderRequest, ProjectBuilderResult
from x8.project_builder.manager import ProjectBuilderManager

router = APIRouter(prefix="/api/project-builder", tags=["project_builder"])


def manager(request: Request, sandbox_path: str = "") -> ProjectBuilderManager:
    settings = request.app.state.settings
    return ProjectBuilderManager(settings.workspace_root, sandbox_path or settings.project_builder_sandbox_path)


@router.post("/preview", response_model=ResultEnvelope[ProjectBuilderResult])
def preview(payload: ProjectBuilderRequest, request: Request) -> ResultEnvelope[ProjectBuilderResult]:
    result = manager(request, payload.sandbox_path).preview(payload)
    return ResultEnvelope(ok=True, status=result.status, data=result, message=result.message, receipts=[Receipt(action="project_builder.preview", status=result.status, summary=result.message, metadata=result.receipt)])


@router.post("/write", response_model=ResultEnvelope[ProjectBuilderResult])
def write(payload: ProjectBuilderRequest, request: Request) -> ResultEnvelope[ProjectBuilderResult]:
    result = manager(request, payload.sandbox_path).write(payload)
    return ResultEnvelope(ok=result.wrote_files, status=result.status, data=result, message=result.message, receipts=[Receipt(action=result.receipt.get("action", "project_builder.write"), status=result.status, summary=result.message, metadata=result.receipt)])
