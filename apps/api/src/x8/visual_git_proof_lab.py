from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from x8.operator_loop_proof import CommandRecord, OperatorProofFailure, _GitRunner, _format_command, _git_env, _redact

LAB_REPO_FULL_NAME = "otiseduncan/x8-git-proof-lab"
LAB_REPO_NAME = "x8-git-proof-lab"
LAB_REMOTE_URL = "https://github.com/otiseduncan/x8-git-proof-lab.git"
LAB_BRANCH = "main"
README_RELATIVE = Path("README.md")
CARD_RELATIVE = Path("proof/live-proof-card.svg")
PROOF_RELATIVE = Path("proof/X8_VISUAL_OPERATOR_PROOF.md")
STATUS_RELATIVE = Path("proof/status.json")
STEPS_RELATIVE = Path("proof/SCREEN_RECORDING_STEPS.md")
RECEIPT_DIR_NAME = "x8-git-proof-lab-receipts"

PREPARE_TRIGGERS = (
    "run the visual x8 git proof lab",
    "prepare the visual x8 git proof lab",
    "prepare visual x8 git proof lab",
    "start the visual x8 git proof lab",
    "start visual x8 git proof lab",
    "update the proof lab readme live",
    "update proof lab readme live",
    "update the proof lab readme",
    "new timestamp and proof card",
    "live timestamp and proof card",
)
APPROVE_PUSH_TRIGGERS = (
    "approve visual x8 git proof lab push",
    "approve x8 git proof lab push",
    "approve visual proof lab push",
)
APPROVE_REPAIR_TRIGGERS = (
    "approve visual x8 git proof lab repair push",
    "approve x8 git proof lab repair push",
    "approve visual proof lab repair push",
)


@dataclass
class VisualProofResult:
    message: str
    status: str
    limitations: list[str] = field(default_factory=list)


@dataclass
class LabWorkspace:
    container_path: Path
    host_path: str


class VisualProofFailure(RuntimeError):
    def __init__(self, message: str, record: CommandRecord | None = None, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.record = record
        self.payload = payload or {}


def is_visual_git_proof_lab_request(message: str) -> bool:
    normalized = _normalize(message)
    return any(trigger in normalized for trigger in (*PREPARE_TRIGGERS, *APPROVE_PUSH_TRIGGERS, *APPROVE_REPAIR_TRIGGERS))


def run_visual_git_proof_lab(message: str) -> VisualProofResult:
    normalized = _normalize(message)
    try:
        if any(trigger in normalized for trigger in APPROVE_REPAIR_TRIGGERS):
            return _approve_repair_push()
        if any(trigger in normalized for trigger in APPROVE_PUSH_TRIGGERS):
            return _approve_initial_push()
        return _prepare_local_write()
    except VisualProofFailure as exc:
        return VisualProofResult(message=_fail_message(exc), status="failed", limitations=[exc.message])
    except OperatorProofFailure as exc:
        converted = VisualProofFailure(exc.message, record=exc.record, payload=exc.payload)
        return VisualProofResult(message=_fail_message(converted), status="failed", limitations=[exc.message])
    except Exception as exc:
        failure = VisualProofFailure(str(exc))
        return VisualProofResult(message=_fail_message(failure), status="failed", limitations=[str(exc)])


def _prepare_local_write() -> VisualProofResult:
    workspace = _ensure_lab_workspace()
    runner = _GitRunner(workspace.container_path)
    run_id = _run_id()
    receipt_dir = _receipt_dir(run_id)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    runner.run(["config", "--global", "--add", "safe.directory", str(workspace.container_path)], allow_global=True)
    runner.run(["config", "user.name", "X8 Visual Proof Lab"])
    runner.run(["config", "user.email", "x8-visual-proof@local"])
    _sync_main_when_possible(runner)

    existing_status = runner.run(["status", "--short"]).stdout.strip()
    if existing_status:
        raise VisualProofFailure(
            "Visual proof lab workspace is dirty before local write. Commit, reset, or clear the lab repo before starting a new proof.",
            payload={"workspace_host_path": workspace.host_path, "git_status_short": existing_status},
        )

    timestamp = _now()
    files = _proof_files(workspace.container_path)
    files["proof"].parent.mkdir(parents=True, exist_ok=True)
    files["readme"].write_text(_readme(run_id, timestamp, "LOCAL_FILE_WRITTEN_BY_X_AWAITING_APPROVAL"), encoding="utf-8")
    files["card"].write_text(_proof_card(run_id, timestamp, "AWAITING OTIS APPROVAL"), encoding="utf-8")
    files["proof"].write_text(_proof(run_id, timestamp, "LOCAL_WRITE", "NOT_REPAIRED_YET"), encoding="utf-8")
    files["steps"].write_text(_steps(), encoding="utf-8")
    _write_json(
        files["status"],
        {
            "run_id": run_id,
            "repo": LAB_REPO_FULL_NAME,
            "phase": "local_file_written_by_x_awaiting_approval",
            "approval_required": True,
            "next_command": "Approve visual X8 git proof lab push",
            "workspace_host_path": workspace.host_path,
            "workspace_container_path": str(workspace.container_path),
            "timestamp": timestamp,
        },
    )

    status_short = runner.run(["status", "--short"]).stdout.strip()
    receipt_path = receipt_dir / "01-local-write-awaiting-approval.json"
    _write_json(
        receipt_path,
        {
            "run_id": run_id,
            "repo": LAB_REPO_FULL_NAME,
            "phase": "local_write_awaiting_user_approval",
            "workspace_host_path": workspace.host_path,
            "workspace_container_path": str(workspace.container_path),
            "git_status_short": status_short,
            "files_written": [_rel(README_RELATIVE), _rel(CARD_RELATIVE), _rel(PROOF_RELATIVE), _rel(STATUS_RELATIVE), _rel(STEPS_RELATIVE)],
            "approval_command": "Approve visual X8 git proof lab push",
            "timestamp": _now(),
        },
    )

    return VisualProofResult(
        message=(
            "AWAITING_APPROVAL\n"
            "visual_step: local_ide_write_complete\n"
            f"repo: {LAB_REPO_FULL_NAME}\n"
            f"local_ide_workspace: {workspace.host_path}\n"
            f"container_workspace: {workspace.container_path}\n"
            f"run_id: {run_id}\n"
            f"files_written: {_rel(README_RELATIVE)}, {_rel(CARD_RELATIVE)}, {_rel(PROOF_RELATIVE)}, {_rel(STATUS_RELATIVE)}, {_rel(STEPS_RELATIVE)}\n"
            f"git_status_short: {status_short}\n"
            f"receipt_path: {_host_receipt_path(receipt_path)}\n"
            "next_command: Approve visual X8 git proof lab push\n"
            "recording_instruction: Show the newly created local_ide_workspace before approving the push."
        ),
        status="awaiting_approval",
    )


def _approve_initial_push() -> VisualProofResult:
    workspace = _lab_workspace_existing()
    runner = _GitRunner(workspace.container_path)
    run_id = _run_id()
    receipt_dir = _receipt_dir(run_id)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    _require_files(workspace.container_path, [README_RELATIVE, CARD_RELATIVE, PROOF_RELATIVE, STATUS_RELATIVE, STEPS_RELATIVE])
    status_before = runner.run(["status", "--short"]).stdout.strip()
    if not status_before:
        raise VisualProofFailure(
            "No local proof-lab changes are waiting for approval. Run 'Run the visual X8 git proof lab' first.",
            payload={"workspace_host_path": workspace.host_path},
        )

    runner.run(["add", _rel(README_RELATIVE), _rel(CARD_RELATIVE), _rel(PROOF_RELATIVE), _rel(STATUS_RELATIVE), _rel(STEPS_RELATIVE)])
    runner.run(["commit", "-m", "proof: X8 writes visual proof lab files"])
    first_commit_sha = runner.run(["rev-parse", "HEAD"]).stdout.strip()
    runner.run(["push", "-u", "origin", LAB_BRANCH], timeout=90)

    receipt_path = receipt_dir / "02-approved-initial-push.json"
    _write_json(
        receipt_path,
        {
            "run_id": run_id,
            "repo": LAB_REPO_FULL_NAME,
            "phase": "approved_initial_push",
            "first_commit_sha": first_commit_sha,
            "github_visual_url": f"https://github.com/{LAB_REPO_FULL_NAME}",
            "workspace_host_path": workspace.host_path,
            "next_command": "Approve visual X8 git proof lab repair push",
            "timestamp": _now(),
        },
    )

    return VisualProofResult(
        message=(
            "PASS\n"
            "visual_step: initial_push_complete\n"
            f"repo: {LAB_REPO_FULL_NAME}\n"
            f"github_visual_url: https://github.com/{LAB_REPO_FULL_NAME}\n"
            f"local_ide_workspace: {workspace.host_path}\n"
            f"first_commit_sha: {first_commit_sha}\n"
            f"receipt_path: {_host_receipt_path(receipt_path)}\n"
            "next_command: Approve visual X8 git proof lab repair push\n"
            "recording_instruction: Refresh GitHub now and show README.md plus proof/live-proof-card.svg."
        ),
        status="passed",
    )


def _approve_repair_push() -> VisualProofResult:
    workspace = _lab_workspace_existing()
    runner = _GitRunner(workspace.container_path)
    run_id = _run_id()
    receipt_dir = _receipt_dir(run_id)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    runner.run(["fetch", "origin", LAB_BRANCH], timeout=90)
    runner.run(["switch", LAB_BRANCH])
    runner.run(["pull", "--ff-only", "origin", LAB_BRANCH], timeout=90)
    pulled_commit_sha = runner.run(["rev-parse", "HEAD"]).stdout.strip()

    timestamp = _now()
    files = _proof_files(workspace.container_path)
    _require_files(workspace.container_path, [README_RELATIVE, CARD_RELATIVE, PROOF_RELATIVE, STATUS_RELATIVE])
    files["readme"].write_text(_readme(run_id, timestamp, "REPAIRED_BY_X_AFTER_PULL"), encoding="utf-8")
    files["card"].write_text(_proof_card(run_id, timestamp, "REPAIRED AFTER PULL"), encoding="utf-8")
    original = files["proof"].read_text(encoding="utf-8")
    repaired = original.replace("REPAIR_STATUS=NOT_REPAIRED_YET", "REPAIR_STATUS=REPAIRED_BY_X_AFTER_PULL")
    if repaired == original:
        repaired += "\nREPAIR_STATUS=REPAIRED_BY_X_AFTER_PULL\n"
    repaired += f"PULLED_COMMIT_SHA={pulled_commit_sha}\nREPAIR_TIMESTAMP={timestamp}\n"
    files["proof"].write_text(repaired, encoding="utf-8")
    _write_json(
        files["status"],
        {
            "run_id": run_id,
            "repo": LAB_REPO_FULL_NAME,
            "phase": "repaired_by_x_after_pull",
            "pulled_commit_sha": pulled_commit_sha,
            "workspace_host_path": workspace.host_path,
            "timestamp": timestamp,
        },
    )

    runner.run(["add", _rel(README_RELATIVE), _rel(CARD_RELATIVE), _rel(PROOF_RELATIVE), _rel(STATUS_RELATIVE)])
    runner.run(["commit", "-m", "repair: X8 repairs visual proof lab after pull"])
    repair_commit_sha = runner.run(["rev-parse", "HEAD"]).stdout.strip()
    runner.run(["push", "origin", LAB_BRANCH], timeout=90)
    final_status = runner.run(["status", "--short"]).stdout.strip()
    final_hash = hashlib.sha256(files["proof"].read_bytes()).hexdigest()

    receipt_path = receipt_dir / "03-approved-repair-push.json"
    _write_json(
        receipt_path,
        {
            "run_id": run_id,
            "repo": LAB_REPO_FULL_NAME,
            "phase": "repair_push_complete",
            "pulled_commit_sha": pulled_commit_sha,
            "repair_commit_sha": repair_commit_sha,
            "final_git_status": final_status,
            "final_proof_file_hash": final_hash,
            "github_visual_url": f"https://github.com/{LAB_REPO_FULL_NAME}",
            "workspace_host_path": workspace.host_path,
            "timestamp": _now(),
        },
    )

    return VisualProofResult(
        message=(
            "PASS\n"
            "visual_step: repair_push_complete\n"
            f"repo: {LAB_REPO_FULL_NAME}\n"
            f"github_visual_url: https://github.com/{LAB_REPO_FULL_NAME}\n"
            f"local_ide_workspace: {workspace.host_path}\n"
            f"pulled_commit_sha: {pulled_commit_sha}\n"
            f"repair_commit_sha: {repair_commit_sha}\n"
            f"final_git_status_short: {final_status or '[clean]'}\n"
            f"receipt_path: {_host_receipt_path(receipt_path)}\n"
            "recording_instruction: Refresh GitHub now and show REPAIR_STATUS=REPAIRED_BY_X_AFTER_PULL."
        ),
        status="passed",
    )


def _ensure_lab_workspace() -> LabWorkspace:
    workspace = _workspace_paths()
    workspace.container_path.parent.mkdir(parents=True, exist_ok=True)
    if not (workspace.container_path / ".git").exists():
        if workspace.container_path.exists() and any(workspace.container_path.iterdir()):
            raise VisualProofFailure(
                "Visual proof lab folder exists but is not a Git repo. Delete it or move it before starting a clean proof.",
                payload={"workspace_host_path": workspace.host_path, "workspace_container_path": str(workspace.container_path)},
            )
        if workspace.container_path.exists():
            workspace.container_path.rmdir()
        _raw_git(["clone", "--branch", LAB_BRANCH, LAB_REMOTE_URL, str(workspace.container_path)], cwd=workspace.container_path.parent, timeout=90)
    else:
        _raw_git(["remote", "set-url", "origin", LAB_REMOTE_URL], cwd=workspace.container_path)
    return workspace


def _lab_workspace_existing() -> LabWorkspace:
    workspace = _workspace_paths()
    if not (workspace.container_path / ".git").exists():
        raise VisualProofFailure(
            "Visual proof lab workspace has not been prepared yet. Run 'Run the visual X8 git proof lab' first.",
            payload={"expected_workspace_host_path": workspace.host_path, "expected_workspace_container_path": str(workspace.container_path)},
        )
    return workspace


def _workspace_paths() -> LabWorkspace:
    container_root = Path("/projects") if Path("/projects").exists() else Path.cwd()
    host_root = (os.getenv("X8_PROJECTS_HOST_ROOT") or os.getenv("X8_WORKSPACE_HOST_ROOT") or "X:/xoduz-sandbox").replace("\\", "/")
    return LabWorkspace(container_path=container_root / LAB_REPO_NAME, host_path=f"{host_root.rstrip('/')}/{LAB_REPO_NAME}")


def _receipt_dir(run_id: str) -> Path:
    root = Path("/projects") if Path("/projects").exists() else Path.cwd()
    return root / RECEIPT_DIR_NAME / run_id


def _sync_main_when_possible(runner: _GitRunner) -> None:
    has_head = runner.exists(["rev-parse", "--verify", "HEAD"])
    if not has_head:
        runner.run(["switch", "-C", LAB_BRANCH])
        return
    runner.run(["fetch", "origin", LAB_BRANCH], timeout=90)
    runner.run(["switch", LAB_BRANCH])
    runner.run(["pull", "--ff-only", "origin", LAB_BRANCH], timeout=90)


def _raw_git(args: list[str], *, cwd: Path, timeout: int = 45) -> CommandRecord:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False, env=_git_env())
    record = CommandRecord(command=["git", *args], cwd=str(cwd), returncode=completed.returncode, stdout=_redact(completed.stdout), stderr=_redact(completed.stderr))
    if record.returncode != 0:
        raise VisualProofFailure("Git command failed.", record=record)
    return record


def _proof_files(root: Path) -> dict[str, Path]:
    return {"readme": root / README_RELATIVE, "card": root / CARD_RELATIVE, "proof": root / PROOF_RELATIVE, "status": root / STATUS_RELATIVE, "steps": root / STEPS_RELATIVE}


def _require_files(root: Path, files: list[Path]) -> None:
    missing = [_rel(path) for path in files if not (root / path).exists()]
    if missing:
        raise VisualProofFailure("Visual proof lab is missing expected files.", payload={"missing_files": missing})


def _readme(run_id: str, timestamp: str, phase: str) -> str:
    return "\n".join([
        "# X8 Git Proof Lab",
        "",
        "![X8 Live Proof Card](proof/live-proof-card.svg)",
        "",
        "This repository exists so X can prove a visible Git workflow on camera.",
        "",
        f"RUN_ID={run_id}",
        f"LAST_UPDATED_UTC={timestamp}",
        f"VISIBLE_PHASE={phase}",
        "PROOF_CARD=proof/live-proof-card.svg",
        "PROOF_FILE=proof/X8_VISUAL_OPERATOR_PROOF.md",
        "STATUS_FILE=proof/status.json",
        "",
        "## What this recording proves",
        "",
        "1. X receives an operator command through chat or voice.",
        "2. X creates/clones a fresh local IDE-visible workspace under `X:/xoduz-sandbox`.",
        "3. X writes this README and proof files before any push approval.",
        "4. Otis reviews the local files in the IDE/cockpit.",
        "5. Otis approves the initial push.",
        "6. X pushes to GitHub so the README and proof card appear on refresh.",
        "7. X pulls from GitHub, repairs the proof, and pushes the repair after approval.",
        "",
    ])


def _proof_card(run_id: str, timestamp: str, phase: str) -> str:
    safe_run_id = run_id.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_timestamp = timestamp.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_phase = phase.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="360" viewBox="0 0 960 360" role="img" aria-label="X8 live Git proof card">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#050505"/>
      <stop offset="45%" stop-color="#18181b"/>
      <stop offset="100%" stop-color="#7f1d1d"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="7" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect width="960" height="360" rx="34" fill="url(#bg)"/>
  <rect x="24" y="24" width="912" height="312" rx="26" fill="rgba(255,255,255,0.035)" stroke="#ef4444" stroke-width="2"/>
  <circle cx="820" cy="86" r="44" fill="#ef4444" opacity="0.85" filter="url(#glow)"/>
  <circle cx="866" cy="132" r="22" fill="#f97316" opacity="0.75" filter="url(#glow)"/>
  <text x="60" y="92" fill="#ffffff" font-family="Segoe UI, Arial, sans-serif" font-size="44" font-weight="800">X8 LIVE GIT PROOF</text>
  <text x="60" y="144" fill="#fca5a5" font-family="Consolas, monospace" font-size="24">README UPDATED BY X</text>
  <text x="60" y="194" fill="#ffffff" font-family="Consolas, monospace" font-size="22">PHASE: {safe_phase}</text>
  <text x="60" y="238" fill="#d4d4d8" font-family="Consolas, monospace" font-size="20">RUN: {safe_run_id}</text>
  <text x="60" y="278" fill="#d4d4d8" font-family="Consolas, monospace" font-size="20">UTC: {safe_timestamp}</text>
  <text x="60" y="318" fill="#22c55e" font-family="Consolas, monospace" font-size="18">LOCAL WRITE FIRST • APPROVAL REQUIRED • GITHUB PUSH SECOND</text>
</svg>
'''


def _proof(run_id: str, timestamp: str, phase: str, repair_status: str) -> str:
    return "\n".join([
        "# X8 Visual Operator Proof",
        "",
        f"RUN_ID={run_id}",
        f"TIMESTAMP_UTC={timestamp}",
        f"PHASE={phase}",
        "LOCAL_IDE_WRITE=WRITTEN_BY_X",
        "USER_APPROVAL_REQUIRED=TRUE",
        f"REPAIR_STATUS={repair_status}",
        "VISUAL_TARGET_REPO=otiseduncan/x8-git-proof-lab",
        "PROOF_CARD=proof/live-proof-card.svg",
        "",
    ])


def _steps() -> str:
    return "\n".join([
        "# Screen Recording Steps",
        "",
        "1. Start with the sandbox proof folder deleted or absent.",
        "2. Open X chat, the 6022 cockpit, and the GitHub repo page side by side.",
        "3. Tell X: `X, update the proof lab README live with a new timestamp and proof card. Do not push yet.`",
        "4. Show X creating/cloning the local proof lab folder and writing README.md plus proof/live-proof-card.svg.",
        "5. Tell X: `Push it to the repo.`",
        "6. Approve the push only after the approval card appears.",
        "7. Refresh GitHub and show the README timestamp and proof card.",
        "8. Approve the repair push, refresh GitHub, and show the repaired status.",
        "",
    ])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _host_receipt_path(path: Path) -> str:
    raw = str(path).replace("\\", "/")
    host_root = (os.getenv("X8_PROJECTS_HOST_ROOT") or os.getenv("X8_WORKSPACE_HOST_ROOT") or "X:/xoduz-sandbox").replace("\\", "/").rstrip("/")
    if raw.startswith("/projects"):
        return raw.replace("/projects", host_root, 1)
    return raw


def _run_id() -> str:
    return f"X8-VISUAL-GIT-PROOF-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", (message or "").strip().lower())


def _fail_message(exc: VisualProofFailure) -> str:
    payload = {"result": "FAIL", "repo": LAB_REPO_FULL_NAME, "error": exc.message, "command_failure": exc.record.as_failure() if exc.record else None, "details": exc.payload}
    return "FAIL\n" + json.dumps(payload, indent=2, sort_keys=True)
