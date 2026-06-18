from fastapi import APIRouter, Request
from pydantic import BaseModel

from x8.adapters.integrations.github_adapter import GitHubAdapter, GitHubStatus
from x8.contracts.base import ResultEnvelope

router = APIRouter(prefix="/api/github", tags=["github"])


class CommitProposalRequest(BaseModel):
    message: str


def adapter(request: Request) -> GitHubAdapter:
    settings = request.app.state.settings
    return GitHubAdapter(settings.github_token, settings.github_owner, settings.github_repo, settings.github_default_branch)


@router.get("/status", response_model=ResultEnvelope[GitHubStatus])
def github_status(request: Request) -> ResultEnvelope[GitHubStatus]:
    data = adapter(request).status()
    return ResultEnvelope(ok=True, status=data.status, data=data, message=data.reason)


@router.get("/repository", response_model=ResultEnvelope[dict[str, str]])
def repository(request: Request) -> ResultEnvelope[dict[str, str]]:
    try:
        data = adapter(request).repository_metadata()
    except Exception as exc:
        return ResultEnvelope(ok=False, status="unavailable", data=None, message=f"GitHub repository metadata failed: {exc}", errors=[str(exc)])
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Repository metadata endpoint available.")


@router.get("/branches", response_model=ResultEnvelope[list[str]])
def branches(request: Request) -> ResultEnvelope[list[str]]:
    try:
        data = adapter(request).branches()
    except Exception as exc:
        return ResultEnvelope(ok=False, status="unavailable", data=None, message=f"GitHub branches failed: {exc}", errors=[str(exc)])
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Branch endpoint available.")


@router.get("/commits", response_model=ResultEnvelope[list[dict[str, str]]])
def commits(request: Request) -> ResultEnvelope[list[dict[str, str]]]:
    try:
        data = adapter(request).commits()
    except Exception as exc:
        return ResultEnvelope(ok=False, status="unavailable", data=None, message=f"GitHub commits failed: {exc}", errors=[str(exc)])
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Recent commits endpoint available.")


@router.get("/user", response_model=ResultEnvelope[dict[str, object]])
def user(request: Request) -> ResultEnvelope[dict[str, object]]:
    try:
        data = adapter(request).authenticated_user()
    except Exception as exc:
        return ResultEnvelope(ok=False, status="unavailable", data=None, message=f"GitHub user check failed: {exc}", errors=[str(exc)])
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Authenticated GitHub user checked.")


@router.get("/file", response_model=ResultEnvelope[dict[str, str]])
def file_fetch(path: str, request: Request) -> ResultEnvelope[dict[str, str]]:
    data = adapter(request).file_fetch(path)
    return ResultEnvelope(ok=True, status=data.get("status", "implemented"), data=data, message=data.get("reason", "GitHub file metadata fetched."))


@router.get("/changed-files", response_model=ResultEnvelope[list[str]])
def changed_files(request: Request) -> ResultEnvelope[list[str]]:
    data = adapter(request).changed_files(request.app.state.settings.workspace_root)
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Changed files inspected from local repository.")


@router.get("/pr-readiness", response_model=ResultEnvelope[dict[str, object]])
def pr_readiness(request: Request) -> ResultEnvelope[dict[str, object]]:
    data = adapter(request).pull_request_readiness(request.app.state.settings.workspace_root)
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Pull request readiness summarized.")


@router.post("/commit-proposal", response_model=ResultEnvelope[dict[str, object]])
def commit_proposal(payload: CommitProposalRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    data = adapter(request).commit_proposal(payload.message, request.app.state.settings.workspace_root)
    return ResultEnvelope(ok=True, status="proposed", data=data, message="Commit proposal created without committing.")
