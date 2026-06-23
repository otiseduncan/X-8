from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRIGGER_PHRASE = "run the full x8 operator loop proof"
DEFAULT_RUN_ID = "X8-OPERATOR-PROOF-20260623-01"
DEFAULT_BRANCH = "x8/operator-proof-20260623-01"
PROOF_FILE_RELATIVE = Path("proof/X8_OPERATOR_LOOP_PROOF.md")
BEFORE_RECEIPT_NAME = "operator-proof-before-push.json"
AFTER_RECEIPT_NAME = "operator-proof-after-repair.json"
GITHUB_TOKEN_ENV_KEYS = (
    "X8_GITHUB_TOKEN",
    "X8_GITHUB_PAT",
    "X8_GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_PAT",
    "GITHUB_API_KEY",
    "CODEX_GITHUB_TOKEN",
    "GIT_TOKEN",
)


@dataclass
class CommandRecord:
    command: list[str]
    cwd: str
    returncode: int
    stdout: str = ""
    stderr: str = ""

    def as_failure(self) -> dict[str, Any]:
        return {
            "command": _format_command(self.command),
            "cwd": self.cwd,
            "returncode": self.returncode,
            "stdout": self.stdout.strip(),
            "stderr": self.stderr.strip(),
        }


@dataclass
class OperatorProofResult:
    message: str
    status: str
    limitations: list[str] = field(default_factory=list)


class OperatorProofFailure(RuntimeError):
    def __init__(self, message: str, record: CommandRecord | None = None, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.record = record
        self.payload = payload or {}


def is_operator_loop_proof_request(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", (message or "").strip().lower())
    return TRIGGER_PHRASE in normalized


def run_operator_loop_proof(message: str, selection: Any | None = None) -> OperatorProofResult:
    run_id = _extract_run_id(message) or DEFAULT_RUN_ID
    branch = _extract_branch(message) or DEFAULT_BRANCH

    try:
        repo_root = _repo_root()
    except OperatorProofFailure as exc:
        return OperatorProofResult(message=_fail_message(exc, branch), status="failed", limitations=[exc.message])

    host_repo_root = _host_repo_root(repo_root)
    sandbox_host_root = (os.getenv("X8_PROJECTS_HOST_ROOT") or "X:/xoduz-sandbox").replace("\\", "/")
    sandbox_container_root = Path("/projects") if Path("/projects").exists() else Path(sandbox_host_root)
    sandbox_dir = sandbox_container_root / "x8-proof" / run_id
    sandbox_host_dir = f"{sandbox_host_root.rstrip('/')}/x8-proof/{run_id}"
    before_receipt_path = sandbox_dir / BEFORE_RECEIPT_NAME
    after_receipt_path = sandbox_dir / AFTER_RECEIPT_NAME
    before_receipt_host_path = f"{sandbox_host_dir}/{BEFORE_RECEIPT_NAME}"
    after_receipt_host_path = f"{sandbox_host_dir}/{AFTER_RECEIPT_NAME}"
    proof_path = repo_root / PROOF_FILE_RELATIVE
    provider = (os.getenv("X8_CHAT_PROVIDER") or os.getenv("CHAT_PROVIDER") or "openwebui").strip() or "openwebui"
    model = getattr(selection, "selected_model", "") or os.getenv("OPENWEBUI_MODEL") or os.getenv("X8_DEFAULT_CHAT_MODEL") or ""
    route = f"{provider}:{model}" if model else provider
    runner = _GitRunner(repo_root)

    try:
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        runner.run(["config", "--global", "--add", "safe.directory", str(repo_root)], allow_global=True)
        runner.run(["rev-parse", "--is-inside-work-tree"])
        initial_branch = runner.run(["branch", "--show-current"]).stdout.strip()
        initial_status = runner.run(["status", "--short"]).stdout.strip()
        if initial_status:
            raise OperatorProofFailure(
                "Repository is dirty before proof run. Refusing to create proof branch from an unclean tree.",
                payload={"initial_branch": initial_branch, "initial_status_short": initial_status, "repo_root": str(repo_root)},
            )

        runner.run(["fetch", "origin", "main"], timeout=90)
        runner.run(["switch", "main"])
        runner.run(["pull", "--ff-only", "origin", "main"], timeout=90)
        if runner.exists(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"]):
            runner.run(["branch", "-D", branch])
        runner.run(["switch", "-c", branch, "origin/main"])
        runner.run(["config", "user.name", "X8 Operator Proof"])
        runner.run(["config", "user.email", "x8-operator-proof@local"])

        timestamp = _now()
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(
            "\n".join(
                [
                    "# X8 Operator Loop Proof",
                    "",
                    f"RUN_ID={run_id}",
                    f"TIMESTAMP={timestamp}",
                    f"WORKSPACE_PATH={host_repo_root}",
                    f"CONTAINER_WORKSPACE_PATH={repo_root}",
                    f"BRANCH_NAME={branch}",
                    f"MODEL_PROVIDER_ROUTE={route}",
                    "PHASE_1_STATUS=WRITTEN_BY_X",
                    "REPAIR_TARGET=NEEDS_REPAIR",
                    "REPAIR_STATUS=NOT_REPAIRED_YET",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        pre_commit_status = runner.run(["status", "--short"]).stdout.strip()
        before_receipt = {
            "run_id": run_id,
            "repo_path": host_repo_root,
            "container_repo_path": str(repo_root),
            "sandbox_path": sandbox_host_dir,
            "container_sandbox_path": str(sandbox_dir),
            "branch": branch,
            "created_file_path": _repo_rel(PROOF_FILE_RELATIVE),
            "git_status": pre_commit_status,
            "timestamp": _now(),
        }
        _write_json(before_receipt_path, before_receipt)

        runner.run(["add", _repo_rel(PROOF_FILE_RELATIVE)])
        runner.run(["commit", "-m", "proof: add X8 operator loop proof artifact"])
        first_commit_sha = runner.run(["rev-parse", "HEAD"]).stdout.strip()
        runner.run(["push", "-u", "--force-with-lease", "origin", branch], timeout=90)

        runner.run(["fetch", "origin", branch], timeout=90)
        runner.run(["pull", "--rebase", "origin", branch], timeout=90)
        if not proof_path.exists():
            raise OperatorProofFailure("Proof file did not exist after pull/rebase from GitHub.")
        pulled_commit_sha = runner.run(["rev-parse", "HEAD"]).stdout.strip()

        repaired = proof_path.read_text(encoding="utf-8")
        repaired = repaired.replace("REPAIR_TARGET=NEEDS_REPAIR", "REPAIR_TARGET=REPAIRED_FROM_PULL")
        repaired = repaired.replace("REPAIR_STATUS=NOT_REPAIRED_YET", "REPAIR_STATUS=REPAIRED_BY_X")
        repaired += f"REPAIR_TIMESTAMP={_now()}\n"
        repaired += f"PULLED_COMMIT_SHA={pulled_commit_sha}\n"
        proof_path.write_text(repaired, encoding="utf-8")

        runner.run(["add", _repo_rel(PROOF_FILE_RELATIVE)])
        runner.run(["commit", "-m", "repair: complete X8 operator loop proof"])
        repair_commit_sha = runner.run(["rev-parse", "HEAD"]).stdout.strip()
        runner.run(["push", "origin", branch], timeout=90)
        final_status = runner.run(["status", "--short"]).stdout.strip()
        final_hash = hashlib.sha256(proof_path.read_bytes()).hexdigest()
        after_receipt = {
            "run_id": run_id,
            "first_commit_sha": first_commit_sha,
            "pulled_commit_sha": pulled_commit_sha,
            "repair_commit_sha": repair_commit_sha,
            "repo_file_path": _repo_rel(PROOF_FILE_RELATIVE),
            "sandbox_receipt_paths": {
                "before_push": before_receipt_host_path,
                "after_repair": after_receipt_host_path,
            },
            "container_sandbox_receipt_paths": {
                "before_push": str(before_receipt_path),
                "after_repair": str(after_receipt_path),
            },
            "final_git_status": final_status,
            "final_proof_file_hash": final_hash,
            "remote_branch": f"origin/{branch}",
            "timestamp": _now(),
        }
        _write_json(after_receipt_path, after_receipt)

        message = _pass_message(
            branch=branch,
            repo_file_path=_repo_rel(PROOF_FILE_RELATIVE),
            before_receipt_path=before_receipt_host_path,
            after_receipt_path=after_receipt_host_path,
            first_commit_sha=first_commit_sha,
            pulled_commit_sha=pulled_commit_sha,
            repair_commit_sha=repair_commit_sha,
            final_status=final_status,
            remote_branch=f"origin/{branch}",
            before_receipt=before_receipt,
            after_receipt=after_receipt,
        )
        return OperatorProofResult(message=message, status="passed")
    except OperatorProofFailure as exc:
        return OperatorProofResult(message=_fail_message(exc, branch), status="failed", limitations=[exc.message])
    except Exception as exc:
        failure = OperatorProofFailure(str(exc))
        return OperatorProofResult(message=_fail_message(failure, branch), status="failed", limitations=[str(exc)])


class _GitRunner:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def run(self, args: list[str], *, timeout: int = 45, allow_global: bool = False) -> CommandRecord:
        if not allow_global:
            _validate_git_args(args)
        completed = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_git_env(),
        )
        record = CommandRecord(
            command=["git", *args],
            cwd=str(self.repo_root),
            returncode=completed.returncode,
            stdout=_redact(completed.stdout),
            stderr=_redact(completed.stderr),
        )
        if record.returncode != 0:
            raise OperatorProofFailure("Git command failed.", record=record)
        return record

    def exists(self, args: list[str]) -> bool:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=_git_env(),
        )
        return completed.returncode == 0


def _validate_git_args(args: list[str]) -> None:
    allowed = {
        "add",
        "branch",
        "commit",
        "config",
        "fetch",
        "log",
        "pull",
        "push",
        "rev-parse",
        "show-ref",
        "status",
        "switch",
    }
    if not args or args[0] not in allowed:
        raise ValueError(f"Unsupported proof git command: {args!r}")


def _repo_root() -> Path:
    candidates: list[Path] = []
    for raw in (
        os.getenv("X8_REPO_ROOT"),
        os.getenv("X8_OPERATOR_REPO_ROOT"),
        os.getenv("X8_WORKSPACE_REPO_ROOT"),
        os.getenv("X8_DOCKER_PRESET_WORKDIR"),
        os.getenv("X8_WORKSPACE_ROOT"),
        "/workspace",
        Path.cwd(),
    ):
        if not raw:
            continue
        path = Path(str(raw)).expanduser()
        if path not in candidates:
            candidates.append(path)

    for candidate in candidates:
        root = _git_toplevel(candidate)
        if root:
            return root

    raise OperatorProofFailure(
        "Could not locate mounted Git repository for operator proof.",
        payload={"candidate_paths": [str(path) for path in candidates]},
    )


def _git_toplevel(candidate: Path) -> Path | None:
    if not candidate.exists():
        return None
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=candidate,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=os.environ.copy() | {"GIT_TERMINAL_PROMPT": "0"},
    )
    if completed.returncode != 0:
        return None
    root = completed.stdout.strip()
    return Path(root).resolve() if root else None


def _host_repo_root(repo_root: Path) -> str:
    configured = (os.getenv("X8_REPO_HOST_ROOT") or "").strip()
    if configured:
        return configured.replace("\\", "/")
    if repo_root == Path("/workspace"):
        return "X:/X 8"
    return str(repo_root).replace("\\", "/")


def _repo_rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def _github_token() -> tuple[str, str]:
    for key in GITHUB_TOKEN_ENV_KEYS:
        value = (os.getenv(key) or "").strip()
        if value:
            return key, value
    return "", ""


def _git_env() -> dict[str, str]:
    env = os.environ.copy() | {
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_ASKPASS": "/bin/false",
    }
    source, token = _github_token()
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
        start = int(env.get("GIT_CONFIG_COUNT") or "0")
        env.update(
            {
                "GIT_CONFIG_COUNT": str(start + 3),
                f"GIT_CONFIG_KEY_{start}": "http.https://github.com/.extraheader",
                f"GIT_CONFIG_VALUE_{start}": f"AUTHORIZATION: basic {basic}",
                f"GIT_CONFIG_KEY_{start + 1}": "credential.helper",
                f"GIT_CONFIG_VALUE_{start + 1}": "",
                f"GIT_CONFIG_KEY_{start + 2}": "x8.authSource",
                f"GIT_CONFIG_VALUE_{start + 2}": source,
            }
        )
    return env


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _extract_run_id(message: str) -> str:
    match = re.search(r"run id:\s*([A-Za-z0-9_.:-]+)", message or "", flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_branch(message: str) -> str:
    match = re.search(r"branch(?: named)?\s*`?([A-Za-z0-9_./-]+)`?", message or "", flags=re.IGNORECASE)
    candidate = match.group(1).strip() if match else ""
    return candidate if candidate.startswith("x8/operator-proof-") else ""


def _redact(value: str) -> str:
    for _, token in [_github_token()]:
        if token:
            value = value.replace(token, "[redacted]")
    for key in GITHUB_TOKEN_ENV_KEYS:
        token = os.getenv(key) or ""
        if token:
            value = value.replace(token, "[redacted]")
    value = re.sub(r"gh[pousr]_[A-Za-z0-9_]+", "[redacted-github-token]", value or "")
    value = re.sub(r"(x-access-token:)[^@\s]+", r"\1[redacted]", value)
    return value


def _format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _pass_message(
    *,
    branch: str,
    repo_file_path: str,
    before_receipt_path: str,
    after_receipt_path: str,
    first_commit_sha: str,
    pulled_commit_sha: str,
    repair_commit_sha: str,
    final_status: str,
    remote_branch: str,
    before_receipt: dict[str, Any],
    after_receipt: dict[str, Any],
) -> str:
    return (
        "PASS\n"
        f"branch: {branch}\n"
        f"repo_proof_file_path: {repo_file_path}\n"
        f"sandbox_before_receipt_path: {before_receipt_path}\n"
        f"sandbox_after_repair_receipt_path: {after_receipt_path}\n"
        f"first_commit_sha: {first_commit_sha}\n"
        f"pulled_commit_sha: {pulled_commit_sha}\n"
        f"repair_commit_sha: {repair_commit_sha}\n"
        f"final_git_status_short: {final_status or '[clean]'}\n"
        f"github_remote_branch_pushed: {remote_branch}\n"
        "errors: []\n\n"
        "before_receipt_json:\n"
        f"```json\n{json.dumps(before_receipt, indent=2, sort_keys=True)}\n```\n\n"
        "after_repair_receipt_json:\n"
        f"```json\n{json.dumps(after_receipt, indent=2, sort_keys=True)}\n```"
    )


def _fail_message(exc: OperatorProofFailure, branch: str) -> str:
    details = dict(exc.payload)
    source, _ = _github_token()
    if source:
        details.setdefault("github_auth_source", source)
    else:
        details.setdefault("github_auth_source", "not available in API container env")
        details.setdefault("checked_env_names", list(GITHUB_TOKEN_ENV_KEYS))
    payload = {
        "result": "FAIL",
        "branch": branch,
        "error": exc.message,
        "command_failure": exc.record.as_failure() if exc.record else None,
        "details": details,
    }
    return "FAIL\n" + json.dumps(payload, indent=2, sort_keys=True)
