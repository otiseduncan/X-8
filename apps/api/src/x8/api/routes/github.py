from fastapi import APIRouter, Request
from pydantic import BaseModel

from x8.adapters.integrations.github_adapter import GitHubAdapter, GitHubStatus
from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.github_ops_manager import GitHubOpsManager

router = APIRouter(prefix="/api/github", tags=["github"])


class CommitProposalRequest(BaseModel):
    message: str


class GitPathRequest(BaseModel):
    path: str = "."
    approved: bool = False


class ConnectRemoteRequest(GitPathRequest):
    remote_url: str


class CreateRepoRequest(BaseModel):
    repo_name: str
    owner: str | None = None
    visibility: str | None = None
    approved: bool = False


def adapter(request: Request) -> GitHubAdapter:
    settings = request.app.state.settings
    return GitHubAdapter(settings.github_token, settings.github_owner, settings.github_repo, settings.github_default_branch)


def ops(request: Request) -> GitHubOpsManager:
    settings = request.app.state.settings
    return GitHubOpsManager(settings.workspace_root, settings.github_token, settings.github_owner, settings.github_default_visibility)


def ops_envelope(data: dict[str, object], message: str) -> ResultEnvelope[dict[str, object]]:
    status = str(data.get("status", "ok"))
    ok = status not in {"blocked", "failed"}
    return ResultEnvelope(
        ok=ok,
        status=status,
        data=data,
        message=str(data.get("reason", message)),
        receipts=[Receipt(action="github.ops", status=status, summary=str(data.get("reason", message)), metadata=data)],
    )


@router.get("/status", response_model=ResultEnvelope[GitHubStatus])
def github_status(request: Request) -> ResultEnvelope[GitHubStatus]:
    data = adapter(request).status()
    return ResultEnvelope(ok=True, status=data.status, data=data, message=data.reason)


@router.get("/ops/auth-status", response_model=ResultEnvelope[dict[str, object]])
def github_ops_auth_status(request: Request) -> ResultEnvelope[dict[str, object]]:
    data = ops(request).auth_status()
    return ResultEnvelope(ok=True, status="ready", data=data, message="GitHub auth status loaded without exposing token.")


@router.get("/ops/status", response_model=ResultEnvelope[dict[str, object]])
def github_ops_status(request: Request) -> ResultEnvelope[dict[str, object]]:
    try:
        data = ops(request).local_status()
    except ValueError as exc:
        return ops_envelope({"status": "blocked", "reason": str(exc)}, "GitHub local status blocked.")
    return ResultEnvelope(ok=True, status="ready", data=data, message="Local git status loaded.")


@router.post("/ops/push-preview", response_model=ResultEnvelope[dict[str, object]])
def github_ops_push_preview(payload: GitPathRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    try:
        data = ops(request).push_preview(payload.path)
    except ValueError as exc:
        return ops_envelope({"status": "blocked", "reason": str(exc)}, "GitHub push preview blocked.")
    return ResultEnvelope(ok=True, status="preview", data=data, message="Push preview loaded without pushing.")


@router.post("/ops/pull-preview", response_model=ResultEnvelope[dict[str, object]])
def github_ops_pull_preview(payload: GitPathRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    try:
        data = ops(request).pull_preview(payload.path)
    except ValueError as exc:
        return ops_envelope({"status": "blocked", "reason": str(exc)}, "GitHub pull preview blocked.")
    return ResultEnvelope(ok=True, status="preview", data=data, message="Pull preview loaded without pulling.")


@router.post("/ops/init", response_model=ResultEnvelope[dict[str, object]])
def github_ops_init(payload: GitPathRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    try:
        data = ops(request).init_repo(payload.path, payload.approved)
    except ValueError as exc:
        data = {"status": "blocked", "reason": str(exc), "changed_files": []}
    return ops_envelope(data, "Git repository init completed.")


@router.post("/ops/connect-remote", response_model=ResultEnvelope[dict[str, object]])
def github_ops_connect_remote(payload: ConnectRemoteRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    try:
        data = ops(request).connect_remote(payload.remote_url, payload.path, payload.approved)
    except ValueError as exc:
        data = {"status": "blocked", "reason": str(exc), "changed_files": []}
    return ops_envelope(data, "Git remote connection completed.")


@router.post("/ops/create-repo", response_model=ResultEnvelope[dict[str, object]])
def github_ops_create_repo(payload: CreateRepoRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    data = ops(request).create_repo(payload.repo_name, payload.visibility, payload.owner, payload.approved)
    return ops_envelope(data, "GitHub repo creation completed.")


@router.post("/ops/pull", response_model=ResultEnvelope[dict[str, object]])
def github_ops_pull(payload: GitPathRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    try:
        data = ops(request).pull(payload.path, payload.approved)
    except ValueError as exc:
        data = {"status": "blocked", "reason": str(exc), "changed_files": []}
    return ops_envelope(data, "Git pull completed.")


@router.post("/ops/push", response_model=ResultEnvelope[dict[str, object]])
def github_ops_push(payload: GitPathRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    try:
        data = ops(request).push(payload.path, payload.approved)
    except ValueError as exc:
        data = {"status": "blocked", "reason": str(exc), "changed_files": []}
    return ops_envelope(data, "Git push completed.")


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
