import base64
import json
import os
import shutil
import subprocess
from pathlib import Path

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


class GitHubProofLabRequest(BaseModel):
    repo_name: str = "x8-git-proof-lab"
    owner: str | None = None
    visibility: str | None = None
    project_path: str | None = None
    validation_path: str | None = None
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


def _blocked(message: str, data: dict[str, object] | None = None) -> ResultEnvelope[dict[str, object]]:
    payload = {"status": "blocked", "reason": message}
    if data:
        payload.update(data)
    return ResultEnvelope(ok=False, status="blocked", data=payload, message=message, receipts=[Receipt(action="github.ops.proof_lab", status="blocked", summary=message, metadata=payload)])


def _safe_rel_path(value: str, fallback: str) -> str:
    candidate = (value or fallback).strip().replace("\\", "/").strip("/")
    if not candidate:
        candidate = fallback
    if ":" in candidate or candidate.startswith("/") or ".." in candidate.split("/"):
        raise ValueError("Proof lab paths must be sandbox-relative.")
    return candidate


def _resolve_under(root: Path, rel_path: str) -> Path:
    target = (root / rel_path).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Proof lab path escapes sandbox root.")
    return target


def _github_basic_auth_header(token: str) -> str:
    encoded = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    return "AUTH" + "ORIZATION: basic " + encoded


def _redact_token(value: str, token: str) -> str:
    if not token:
        return value
    token_basic = _github_basic_auth_header(token).split("basic ", 1)[-1]
    return value.replace(token, "[redacted]").replace(token_basic, "[redacted-basic]")


def _run_git(args: list[str], cwd: Path, token: str = "", timeout: int = 60) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    if token:
        env["GIT_CONFIG_COUNT"] = "3"
        env["GIT_CONFIG_KEY_0"] = "credential.helper"
        env["GIT_CONFIG_VALUE_0"] = ""
        env["GIT_CONFIG_KEY_1"] = "http.https://github.com/.extraheader"
        env["GIT_CONFIG_VALUE_1"] = _github_basic_auth_header(token)
        env["GIT_CONFIG_KEY_2"] = "url.https://github.com/.insteadOf"
        env["GIT_CONFIG_VALUE_2"] = "git@github.com:"
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False, env=env)


def _run_checked(args: list[str], cwd: Path, token: str = "", timeout: int = 60) -> dict[str, object]:
    result = _run_git(args, cwd, token=token, timeout=timeout)
    stdout = _redact_token(result.stdout.strip(), token)
    stderr = _redact_token(result.stderr.strip(), token)
    return {"cmd": "git " + " ".join(args), "auth": "github-token" if token else "none", "returncode": result.returncode, "stdout": stdout, "stderr": stderr}


def _ensure_ok(record: dict[str, object]) -> None:
    if int(record.get("returncode", 1)) != 0:
        detail = str(record.get("stderr") or record.get("stdout") or "git command failed")
        raise RuntimeError(f"{record.get('cmd')}: {detail}")


def _git_output(args: list[str], cwd: Path, token: str = "") -> str:
    record = _run_checked(args, cwd, token=token)
    _ensure_ok(record)
    return str(record.get("stdout") or "")


def _write_proof_files(project_dir: Path, repo_name: str, round_trip: int) -> None:
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "README.md").write_text(
        f"# {repo_name}\n\nDedicated GitHub round-trip proof repository for X/Xoduz sandbox push, pull, clone, and subsequent push validation.\n",
        encoding="utf-8",
    )
    (project_dir / "src" / "index.js").write_text("console.log('x8 git proof lab');\n", encoding="utf-8")
    proof = {"project": repo_name, "sandboxWrite": True, "gitHubProof": True, "roundTrip": round_trip}
    (project_dir / "proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")


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


@router.post("/ops/proof-lab", response_model=ResultEnvelope[dict[str, object]])
def github_ops_proof_lab(payload: GitHubProofLabRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    settings = request.app.state.settings
    repo_name = GitHubOpsManager(settings.workspace_root, settings.github_token, settings.github_owner, settings.github_default_visibility)._sanitize_repo_name(payload.repo_name)
    if not payload.approved:
        return _blocked("Approval required before GitHub proof lab writes.", {"repo_name": repo_name})
    if not repo_name.startswith("x8-git-proof"):
        return _blocked("Proof lab is restricted to dedicated repositories named x8-git-proof*.", {"repo_name": repo_name})
    if not settings.github_token:
        return _blocked("GitHub token is not configured in the X8 runtime.", {"repo_name": repo_name})

    owner = payload.owner or settings.github_owner or "otiseduncan"
    visibility = payload.visibility or settings.github_default_visibility
    if visibility not in {"private", "public"}:
        visibility = "private"

    root = Path(settings.workspace_root).resolve()
    project_rel = _safe_rel_path(payload.project_path or repo_name, repo_name)
    validation_rel = _safe_rel_path(payload.validation_path or f"{repo_name}-pull-validation", f"{repo_name}-pull-validation")
    project_dir = _resolve_under(root, project_rel)
    validation_dir = _resolve_under(root, validation_rel)
    if project_dir == validation_dir:
        return _blocked("Project and validation paths must be different.", {"repo_name": repo_name})

    commands: list[dict[str, object]] = []
    try:
        if project_dir.exists():
            shutil.rmtree(project_dir)
        if validation_dir.exists():
            shutil.rmtree(validation_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        _write_proof_files(project_dir, repo_name, 1)

        def run(args: list[str], cwd: Path, token: str = "", timeout: int = 60) -> str:
            record = _run_checked(args, cwd, token=token, timeout=timeout)
            commands.append(record)
            _ensure_ok(record)
            return str(record.get("stdout") or "")

        run(["init"], project_dir)
        run(["branch", "-M", "main"], project_dir)
        run(["config", "user.name", "X8 Sandbox Proof"], project_dir)
        run(["config", "user.email", "x8-sandbox-proof@localhost"], project_dir)
        run(["add", "README.md", "src/index.js", "proof.json"], project_dir)
        run(["commit", "-m", "Initial sandbox GitHub proof"], project_dir)
        first_sha = run(["rev-parse", "HEAD"], project_dir).strip()

        create_result = ops(request).create_repo(repo_name, visibility, owner, approved=True)
        create_status = str(create_result.get("status", ""))
        likely_exists = bool(create_result.get("likely_repo_already_exists"))
        if create_status == "blocked" and not likely_exists:
            return _blocked(str(create_result.get("reason", "GitHub repository creation failed.")), create_result)

        remote_url = f"https://github.com/{owner}/{repo_name}.git"
        html_url = f"https://github.com/{owner}/{repo_name}"
        run(["remote", "add", "origin", remote_url], project_dir)
        run(["push", "-u", "origin", "main", "--force"], project_dir, token=settings.github_token, timeout=120)

        run(["clone", remote_url, str(validation_dir)], root, token=settings.github_token, timeout=120)
        for rel_file in ["README.md", "src/index.js", "proof.json"]:
            if not (validation_dir / rel_file).exists():
                raise RuntimeError(f"Validation clone missing {rel_file}")

        _write_proof_files(project_dir, repo_name, 2)
        run(["add", "proof.json"], project_dir)
        run(["commit", "-m", "Verify second sandbox GitHub push"], project_dir)
        second_sha = run(["rev-parse", "HEAD"], project_dir).strip()
        run(["push", "origin", "main"], project_dir, token=settings.github_token, timeout=120)
        project_status = run(["status", "--short", "--branch"], project_dir)

        run(["pull", "--ff-only"], validation_dir, token=settings.github_token, timeout=120)
        validation_status = run(["status", "--short", "--branch"], validation_dir)
        final_proof = json.loads((validation_dir / "proof.json").read_text(encoding="utf-8"))
        if final_proof.get("roundTrip") != 2:
            raise RuntimeError("Validation proof.json did not update to roundTrip = 2")

    except Exception as exc:
        data = {
            "status": "failed",
            "reason": str(exc),
            "repo_name": repo_name,
            "sandbox_root": str(root),
            "project_absolute_path": str(project_dir),
            "validation_absolute_path": str(validation_dir),
            "commands": commands,
        }
        return ResultEnvelope(ok=False, status="failed", data=data, message=str(exc), receipts=[Receipt(action="github.ops.proof_lab", status="failed", summary=str(exc), metadata=data)])

    data = {
        "status": "passed",
        "sandbox_root": str(root),
        "host_sandbox_root": settings.projects_host_root or settings.workspace_host_root or "UNSET",
        "repo_name": repo_name,
        "github_repo_url": html_url,
        "project_path": project_rel,
        "validation_path": validation_rel,
        "project_absolute_path": str(project_dir),
        "validation_absolute_path": str(validation_dir),
        "first_commit_sha": first_sha,
        "second_commit_sha": second_sha,
        "project_status_after_second_push": project_status,
        "validation_status_after_pull": validation_status,
        "final_proof_json": final_proof,
        "repo_created_or_reused": "reused" if likely_exists else "created",
        "commands": commands,
    }
    return ResultEnvelope(ok=True, status="passed", data=data, message="GitHub proof lab completed and verified.", receipts=[Receipt(action="github.ops.proof_lab", status="passed", summary="GitHub proof lab completed and verified.", metadata=data)])


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
