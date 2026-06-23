from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from x8.api.routes.github import (
    GitHubProofLabRequest,
    _blocked,
    _ensure_ok,
    _resolve_under,
    _run_checked,
    _safe_rel_path,
    github_ops_proof_lab,
    ops,
)
from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.github_ops_manager import GitHubOpsManager

router = APIRouter(prefix="/api/github", tags=["github"])


def _run_validation(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["python", "tests/test_x8_demo.py"],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    summary = "PASS" if completed.returncode == 0 else "FAIL"
    detail = (stdout or stderr or "no validation output").replace("\n", " | ")
    return {
        "ok": completed.returncode == 0,
        "summary": f"{summary}: {detail}",
        "command": {
            "cmd": "python tests/test_x8_demo.py",
            "cwd": str(path),
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _live_response(status: str, message: str, data: dict[str, object]) -> ResultEnvelope[dict[str, object]]:
    return ResultEnvelope(
        ok=status == "passed",
        status=status,
        data=data,
        message=message,
        receipts=[Receipt(action="github.ops.live_repo_proof", status=status, summary=message, metadata=data)],
    )


def _approve_live_repo_proof(payload: GitHubProofLabRequest, request: Request, repo_name: str) -> ResultEnvelope[dict[str, object]]:
    settings = request.app.state.settings

    if not payload.approved:
        return _blocked(
            "Approval required before creating the brand-new GitHub repo and pushing X8 local work.",
            {"repo_name": repo_name},
        )

    if not settings.github_token:
        return _blocked("GitHub token is not configured in the X8 runtime.", {"repo_name": repo_name})

    owner = payload.owner or settings.github_owner or "otiseduncan"
    visibility = payload.visibility or settings.github_default_visibility
    if visibility not in {"private", "public"}:
        visibility = "private"

    root = Path(settings.workspace_root).resolve()
    project_rel = _safe_rel_path(payload.project_path or repo_name, repo_name)
    validation_rel = _safe_rel_path(
        payload.validation_path or f"{repo_name}-pull-validation",
        f"{repo_name}-pull-validation",
    )
    project_dir = _resolve_under(root, project_rel)
    validation_dir = _resolve_under(root, validation_rel)

    if project_dir == validation_dir:
        return _blocked("Project and validation paths must be different.", {"repo_name": repo_name})

    if not project_dir.exists():
        return _blocked(
            "The live proof workspace does not exist yet. Start a brand new live repo proof first.",
            {"repo_name": repo_name, "project_path": project_rel},
        )

    if not (project_dir / "src" / "x8_demo.py").exists() or not (project_dir / "tests" / "test_x8_demo.py").exists():
        return _blocked(
            "The live proof workspace is missing the expected code/test files.",
            {"repo_name": repo_name, "project_path": project_rel},
        )

    commands: list[dict[str, object]] = []

    def run(args: list[str], cwd: Path, token: str = "", timeout: int = 60) -> str:
        record = _run_checked(args, cwd, token=token, timeout=timeout)
        commands.append(record)
        _ensure_ok(record)
        return str(record.get("stdout") or "")

    try:
        pre_push_validation = _run_validation(project_dir)
        if not pre_push_validation["ok"]:
            return _live_response(
                "failed",
                "Live proof push blocked because validation is still failing.",
                {
                    "status": "failed",
                    "reason": "Validation must pass before GitHub creation/push.",
                    "repo_name": repo_name,
                    "project_path": project_rel,
                    "project_absolute_path": str(project_dir),
                    "pre_push_validation": pre_push_validation,
                },
            )

        run(["branch", "-M", "main"], project_dir)
        run(["config", "user.name", "X8 Live Repo Proof"], project_dir)
        run(["config", "user.email", "x8-live-proof@local"], project_dir)
        run(
            [
                "add",
                "README.md",
                "src/x8_demo.py",
                "tests/test_x8_demo.py",
                "proof/status.json",
                "proof/live-proof-card.svg",
                "proof/repair-report.md",
            ],
            project_dir,
        )

        commit_record = _run_checked(["commit", "-m", "Create repaired X8 live proof repo"], project_dir)
        commands.append(commit_record)
        combined_commit_output = str(commit_record.get("stdout", "")) + str(commit_record.get("stderr", ""))
        if int(commit_record.get("returncode", 1)) != 0 and "nothing to commit" not in combined_commit_output.lower():
            _ensure_ok(commit_record)

        first_sha = run(["rev-parse", "HEAD"], project_dir).strip()

        create_result = ops(request).create_repo(repo_name, visibility, owner, approved=True)
        create_status = str(create_result.get("status", ""))
        likely_exists = bool(create_result.get("likely_repo_already_exists"))
        if create_status == "blocked":
            return _blocked(str(create_result.get("reason", "GitHub repository creation failed.")), create_result)

        remote_url = f"https://github.com/{owner}/{repo_name}.git"
        html_url = f"https://github.com/{owner}/{repo_name}"

        remote_check = _run_checked(["remote", "get-url", "origin"], project_dir)
        commands.append(remote_check)
        if int(remote_check.get("returncode", 1)) == 0:
            run(["remote", "set-url", "origin", remote_url], project_dir)
        else:
            run(["remote", "add", "origin", remote_url], project_dir)

        run(["push", "-u", "origin", "main"], project_dir, token=settings.github_token, timeout=120)
        project_status_after_push = run(["status", "--short", "--branch"], project_dir)

        if validation_dir.exists():
            shutil.rmtree(validation_dir)

        run(["clone", remote_url, str(validation_dir)], root, token=settings.github_token, timeout=120)

        pullback_validation = _run_validation(validation_dir)
        validation_status_after_pull = run(["status", "--short", "--branch"], validation_dir)

        final_status_path = validation_dir / "proof" / "status.json"
        final_status_json = json.loads(final_status_path.read_text(encoding="utf-8")) if final_status_path.exists() else {}

        if not pullback_validation["ok"]:
            raise RuntimeError(f"Pull-back validation failed: {pullback_validation['summary']}")

        _write_json(
            root / f"{repo_name}-receipts" / "03-github-create-push-pull-verified.json",
            {
                "repo_name": repo_name,
                "github_repo_url": html_url,
                "project_path": project_rel,
                "validation_path": validation_rel,
                "project_absolute_path": str(project_dir),
                "validation_absolute_path": str(validation_dir),
                "pre_push_validation": pre_push_validation,
                "pullback_validation": pullback_validation,
                "final_status_json": final_status_json,
                "first_commit_sha": first_sha,
                "repo_created_or_reused": "reused" if likely_exists else "created",
                "commands": commands,
            },
        )

    except Exception as exc:
        return _live_response(
            "failed",
            str(exc),
            {
                "status": "failed",
                "reason": str(exc),
                "repo_name": repo_name,
                "sandbox_root": str(root),
                "project_path": project_rel,
                "validation_path": validation_rel,
                "project_absolute_path": str(project_dir),
                "validation_absolute_path": str(validation_dir),
                "commands": commands,
            },
        )

    return _live_response(
        "passed",
        "Brand-new live repo proof created, pushed, pulled back, and verified.",
        {
            "status": "passed",
            "proof_mode": "brand_new_live_repo",
            "sandbox_root": str(root),
            "host_sandbox_root": settings.projects_host_root or settings.workspace_host_root or "UNSET",
            "repo_name": repo_name,
            "github_repo_url": html_url,
            "project_path": project_rel,
            "validation_path": validation_rel,
            "project_absolute_path": str(project_dir),
            "validation_absolute_path": str(validation_dir),
            "first_commit_sha": first_sha,
            "project_status_after_second_push": project_status_after_push,
            "validation_status_after_pull": validation_status_after_pull,
            "pre_push_validation": pre_push_validation,
            "pullback_validation": pullback_validation,
            "final_proof_json": final_status_json,
            "repo_created_or_reused": "reused" if likely_exists else "created",
            "commands": commands,
        },
    )


@router.post("/ops/proof-lab", response_model=ResultEnvelope[dict[str, object]])
def github_ops_proof_lab_live_repo_bridge(payload: GitHubProofLabRequest, request: Request) -> ResultEnvelope[dict[str, object]]:
    settings = request.app.state.settings
    repo_name = GitHubOpsManager(
        settings.workspace_root,
        settings.github_token,
        settings.github_owner,
        settings.github_default_visibility,
    )._sanitize_repo_name(payload.repo_name)

    if repo_name.startswith("x8-live-proof-"):
        return _approve_live_repo_proof(payload, request, repo_name)

    return github_ops_proof_lab(payload, request)
