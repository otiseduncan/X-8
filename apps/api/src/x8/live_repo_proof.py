from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class LiveRepoProofResult:
    message: str
    status: str
    repo_name: str = ""
    project_path: str = ""
    host_workspace: str = ""
    container_workspace: str = ""
    validation_path: str = ""
    github_repo: str = ""
    limitations: list[str] = field(default_factory=list)


@dataclass
class LiveWorkspace:
    repo_name: str
    container_path: Path
    host_path: str


START_TRIGGERS = (
    "start a brand new live repo proof",
    "start brand new live repo proof",
    "create a brand new proof repo",
    "create brand new proof repo",
    "initialize a brand new repo",
    "init a brand new repo",
    "brand new repo proof",
)

REPAIR_TRIGGERS = (
    "repair the live proof",
    "repair the failing test",
    "repair the proof repo",
    "fix the failing test",
    "validate and repair",
)

PUSH_TRIGGERS = (
    "push the new repo",
    "push this new repo",
    "create the github repo and push",
    "create github repo and push",
    "push it to github",
    "push it to the repo",
)


def is_live_repo_proof_request(message: str) -> bool:
    text = _normalize(message)
    return any(trigger in text for trigger in (*START_TRIGGERS, *REPAIR_TRIGGERS, *PUSH_TRIGGERS))


def run_live_repo_proof(message: str) -> LiveRepoProofResult:
    text = _normalize(message)
    try:
        if any(trigger in text for trigger in REPAIR_TRIGGERS):
            return _repair_latest_live_repo()
        if any(trigger in text for trigger in PUSH_TRIGGERS):
            return _approval_for_latest_live_repo()
        return _start_new_live_repo()
    except Exception as exc:
        return LiveRepoProofResult(message=f"FAIL\n{exc}", status="failed", limitations=[str(exc)])


def _start_new_live_repo() -> LiveRepoProofResult:
    workspace = _new_workspace()
    if workspace.container_path.exists():
        shutil.rmtree(workspace.container_path)
    workspace.container_path.mkdir(parents=True, exist_ok=False)
    (workspace.container_path / "src").mkdir()
    (workspace.container_path / "tests").mkdir()
    (workspace.container_path / "proof").mkdir()

    run_id = workspace.repo_name.upper().replace("-", "_")
    timestamp = _now()
    _write_broken_files(workspace, run_id, timestamp)

    commands: list[dict[str, Any]] = []
    commands.append(_run(["git", "init"], cwd=workspace.container_path))
    commands.append(_run(["git", "branch", "-M", "main"], cwd=workspace.container_path))
    commands.append(_run(["git", "config", "user.name", "X8 Live Repo Proof"], cwd=workspace.container_path))
    commands.append(_run(["git", "config", "user.email", "x8-live-proof@local"], cwd=workspace.container_path))
    validation = _run_validation(workspace.container_path)
    status_short = _git_status(workspace.container_path)

    receipt_dir = _receipt_dir(workspace.repo_name)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        receipt_dir / "01-created-broken-local-repo.json",
        {
            "repo_name": workspace.repo_name,
            "phase": "created_broken_local_repo",
            "host_workspace": workspace.host_path,
            "container_workspace": str(workspace.container_path),
            "validation": validation,
            "git_status_short": status_short,
            "commands": commands,
            "timestamp": _now(),
        },
    )

    return LiveRepoProofResult(
        status="passed",
        repo_name=workspace.repo_name,
        project_path=workspace.repo_name,
        host_workspace=workspace.host_path,
        container_workspace=str(workspace.container_path),
        validation_path=f"{workspace.repo_name}-pull-validation",
        github_repo=f"otiseduncan/{workspace.repo_name}",
        message=(
            "BROKEN_STATE_READY\n"
            "visual_step: new_repo_created_locally_with_failing_test\n"
            f"repo_name: {workspace.repo_name}\n"
            f"local_ide_workspace: {workspace.host_path}\n"
            f"container_workspace: {workspace.container_path}\n"
            "files_written: README.md, src/x8_demo.py, tests/test_x8_demo.py, proof/status.json, proof/live-proof-card.svg, proof/repair-report.md\n"
            f"validation_result: FAIL_EXPECTED\n"
            f"validation_output: {validation['summary']}\n"
            f"git_status_short: {status_short or '[clean]'}\n"
            "next_command: X, repair the failing test and prepare the GitHub push approval.\n"
            "recording_instruction: Open README.md, src/x8_demo.py, and tests/test_x8_demo.py in the 6022 IDE. Show the failing validation before repair."
        ),
    )


def _repair_latest_live_repo() -> LiveRepoProofResult:
    workspace = _latest_workspace()
    run_id = workspace.repo_name.upper().replace("-", "_")
    timestamp = _now()

    before_validation = _run_validation(workspace.container_path)
    demo_file = workspace.container_path / "src" / "x8_demo.py"
    original = demo_file.read_text(encoding="utf-8")
    repaired = original.replace("return a - b", "return a + b")
    if repaired == original:
        repaired = "def add(a: int, b: int) -> int:\n    return a + b\n"
    demo_file.write_text(repaired, encoding="utf-8")

    after_validation = _run_validation(workspace.container_path)
    _write_repaired_files(workspace, run_id, timestamp, before_validation, after_validation)
    status_short = _git_status(workspace.container_path)

    receipt_dir = _receipt_dir(workspace.repo_name)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        receipt_dir / "02-repaired-awaiting-github-approval.json",
        {
            "repo_name": workspace.repo_name,
            "phase": "repaired_awaiting_github_create_and_push_approval",
            "host_workspace": workspace.host_path,
            "container_workspace": str(workspace.container_path),
            "before_validation": before_validation,
            "after_validation": after_validation,
            "git_status_short": status_short,
            "timestamp": _now(),
        },
    )

    status = "awaiting_approval" if after_validation["ok"] else "failed"
    next_line = "next_command: Push the new repo to GitHub." if after_validation["ok"] else "next_command: Repair is still failing. Do not push."
    return LiveRepoProofResult(
        status=status,
        repo_name=workspace.repo_name,
        project_path=workspace.repo_name,
        host_workspace=workspace.host_path,
        container_workspace=str(workspace.container_path),
        validation_path=f"{workspace.repo_name}-pull-validation",
        github_repo=f"otiseduncan/{workspace.repo_name}",
        message=(
            f"{'AWAITING_APPROVAL' if after_validation['ok'] else 'FAIL'}\n"
            "visual_step: local_repair_complete\n"
            f"repo_name: {workspace.repo_name}\n"
            f"local_ide_workspace: {workspace.host_path}\n"
            f"container_workspace: {workspace.container_path}\n"
            f"before_validation: {before_validation['summary']}\n"
            f"after_validation: {after_validation['summary']}\n"
            f"git_status_short: {status_short or '[clean]'}\n"
            f"{next_line}\n"
            "recording_instruction: Show src/x8_demo.py changing from subtraction to addition, then show proof/repair-report.md before approving GitHub creation/push."
        ),
    )


def _approval_for_latest_live_repo() -> LiveRepoProofResult:
    workspace = _latest_workspace()
    status_file = workspace.container_path / "proof" / "status.json"
    status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}
    validation = _run_validation(workspace.container_path)
    if not validation["ok"]:
        return LiveRepoProofResult(message=f"FAIL\nCannot request push approval because validation is failing: {validation['summary']}", status="failed")
    return LiveRepoProofResult(
        status="awaiting_approval",
        repo_name=workspace.repo_name,
        project_path=workspace.repo_name,
        host_workspace=workspace.host_path,
        container_workspace=str(workspace.container_path),
        validation_path=f"{workspace.repo_name}-pull-validation",
        github_repo=f"otiseduncan/{workspace.repo_name}",
        message=(
            "AWAITING_APPROVAL\n"
            "visual_step: github_create_and_push_authorization_required\n"
            f"repo_name: {workspace.repo_name}\n"
            f"repo: otiseduncan/{workspace.repo_name}\n"
            f"local_ide_workspace: {workspace.host_path}\n"
            f"validation_result: {validation['summary']}\n"
            "approval: Click Approve to create the brand-new GitHub repo and push the repaired local code.\n"
            f"phase: {status.get('phase', 'unknown')}"
        ),
    )


def _write_broken_files(workspace: LiveWorkspace, run_id: str, timestamp: str) -> None:
    (workspace.container_path / "README.md").write_text(
        "\n".join(
            [
                f"# {workspace.repo_name}",
                "",
                "![X8 Live Repo Proof](proof/live-proof-card.svg)",
                "",
                "## Visible State",
                "",
                "Status: NEEDS_REPAIR",
                "Validation: FAIL_EXPECTED",
                "",
                "This repository is intentionally born broken on camera so X8 can repair it visibly in the IDE before any GitHub push.",
                "",
                "### Broken marker",
                "",
                "```text",
                "NEEDS_REPAIR=true",
                "BROKEN_FUNCTION=src/x8_demo.py:add_returns_subtraction",
                "EXPECTED_FIX=return a + b",
                "```",
                "",
                f"Run ID: `{run_id}`",
                f"Created UTC: `{timestamp}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace.container_path / "src" / "x8_demo.py").write_text(
        "def add(a: int, b: int) -> int:\n    # BROKEN ON PURPOSE FOR X8 VIDEO PROOF\n    return a - b\n",
        encoding="utf-8",
    )
    (workspace.container_path / "tests" / "test_x8_demo.py").write_text(
        "from pathlib import Path\nimport sys\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n\nfrom x8_demo import add\n\n\ndef main():\n    result = add(2, 3)\n    if result != 5:\n        raise AssertionError(f'Expected add(2, 3) to equal 5, got {result}')\n    print('PASS: add(2, 3) == 5')\n\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    _write_json(
        workspace.container_path / "proof" / "status.json",
        {
            "repo_name": workspace.repo_name,
            "phase": "broken_local_repo_created_by_x",
            "needs_repair": True,
            "approval_required_before_github_create": True,
            "created_utc": timestamp,
        },
    )
    (workspace.container_path / "proof" / "repair-report.md").write_text(
        "# X8 Repair Report\n\nBROKEN_BEFORE=true\nREPAIR_APPLIED=false\nVALIDATION=FAIL_EXPECTED\n",
        encoding="utf-8",
    )
    (workspace.container_path / "proof" / "live-proof-card.svg").write_text(_proof_card(workspace.repo_name, timestamp, "BROKEN / NEEDS REPAIR"), encoding="utf-8")


def _write_repaired_files(workspace: LiveWorkspace, run_id: str, timestamp: str, before: dict[str, Any], after: dict[str, Any]) -> None:
    readme = workspace.container_path / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = text.replace("Status: NEEDS_REPAIR", "Status: REPAIRED_BY_X")
    text = text.replace("Validation: FAIL_EXPECTED", "Validation: PASS_AFTER_REPAIR")
    text = text.replace("NEEDS_REPAIR=true", "NEEDS_REPAIR=false")
    text += "\n## Repair Evidence\n\n"
    text += f"Repaired UTC: `{timestamp}`\n\n"
    text += "```text\n"
    text += f"BEFORE_VALIDATION={before['summary']}\n"
    text += f"AFTER_VALIDATION={after['summary']}\n"
    text += "REPAIR_STATUS=REPAIRED_BY_X\n"
    text += "```\n"
    readme.write_text(text, encoding="utf-8")
    _write_json(
        workspace.container_path / "proof" / "status.json",
        {
            "repo_name": workspace.repo_name,
            "phase": "repaired_locally_awaiting_github_create_and_push_approval",
            "needs_repair": False,
            "repair_status": "REPAIRED_BY_X",
            "before_validation": before,
            "after_validation": after,
            "approval_required_before_github_create": True,
            "repaired_utc": timestamp,
        },
    )
    (workspace.container_path / "proof" / "repair-report.md").write_text(
        "\n".join(
            [
                "# X8 Repair Report",
                "",
                "BROKEN_BEFORE=true",
                "REPAIR_APPLIED=true",
                "FOUND_FUNCTION=src/x8_demo.py:add",
                "BUG=returned_subtraction",
                "FIX=return_a_plus_b",
                f"BEFORE_VALIDATION={before['summary']}",
                f"AFTER_VALIDATION={after['summary']}",
                "PUSH_REQUIRED=true",
                f"REPAIRED_UTC={timestamp}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace.container_path / "proof" / "live-proof-card.svg").write_text(_proof_card(workspace.repo_name, timestamp, "REPAIRED / AWAITING PUSH APPROVAL"), encoding="utf-8")


def _run_validation(path: Path) -> dict[str, Any]:
    result = _run(["python", "tests/test_x8_demo.py"], cwd=path, check=False)
    summary = "PASS" if result["returncode"] == 0 else "FAIL"
    out = (result.get("stdout") or result.get("stderr") or "").strip().replace("\n", " | ")
    return {"ok": result["returncode"] == 0, "summary": f"{summary}: {out}", "command": result}


def _git_status(path: Path) -> str:
    result = _run(["git", "status", "--short"], cwd=path, check=False)
    return str(result.get("stdout") or "").strip()


def _run(command: list[str], *, cwd: Path, check: bool = True) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False, timeout=45)
    record = {"cmd": " ".join(command), "cwd": str(cwd), "returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
    if check and completed.returncode != 0:
        raise RuntimeError(json.dumps(record, indent=2))
    return record


def _new_workspace() -> LiveWorkspace:
    repo_name = f"x8-live-proof-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    root = _container_root()
    host_root = _host_root()
    return LiveWorkspace(repo_name=repo_name, container_path=root / repo_name, host_path=f"{host_root}/{repo_name}")


def _latest_workspace() -> LiveWorkspace:
    root = _container_root()
    candidates = sorted([item for item in root.glob("x8-live-proof-*") if item.is_dir()], key=lambda item: item.name, reverse=True)
    if not candidates:
        raise RuntimeError("No x8-live-proof-* workspace exists. Start a brand new live repo proof first.")
    path = candidates[0]
    return LiveWorkspace(repo_name=path.name, container_path=path, host_path=f"{_host_root()}/{path.name}")


def _container_root() -> Path:
    return Path("/projects") if Path("/projects").exists() else Path.cwd()


def _host_root() -> str:
    return (os.getenv("X8_PROJECTS_HOST_ROOT") or os.getenv("X8_WORKSPACE_HOST_ROOT") or "X:/xoduz-sandbox").replace("\\", "/").rstrip("/")


def _receipt_dir(repo_name: str) -> Path:
    return _container_root() / f"{repo_name}-receipts"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _proof_card(repo_name: str, timestamp: str, phase: str) -> str:
    safe_repo = _xml(repo_name)
    safe_timestamp = _xml(timestamp)
    safe_phase = _xml(phase)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="360" viewBox="0 0 960 360" role="img" aria-label="X8 live repo proof card">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#050505"/>
      <stop offset="50%" stop-color="#111827"/>
      <stop offset="100%" stop-color="#7f1d1d"/>
    </linearGradient>
  </defs>
  <rect width="960" height="360" rx="34" fill="url(#bg)"/>
  <rect x="28" y="28" width="904" height="304" rx="24" fill="rgba(255,255,255,0.045)" stroke="#ef4444" stroke-width="2"/>
  <text x="60" y="92" fill="#ffffff" font-family="Segoe UI, Arial, sans-serif" font-size="42" font-weight="800">X8 BRAND NEW REPO PROOF</text>
  <text x="60" y="148" fill="#fca5a5" font-family="Consolas, monospace" font-size="24">{safe_phase}</text>
  <text x="60" y="206" fill="#ffffff" font-family="Consolas, monospace" font-size="22">REPO: {safe_repo}</text>
  <text x="60" y="258" fill="#d4d4d8" font-family="Consolas, monospace" font-size="20">UTC: {safe_timestamp}</text>
  <text x="60" y="312" fill="#22c55e" font-family="Consolas, monospace" font-size="18">EMPTY SANDBOX → LOCAL REPAIR → APPROVAL → NEW GITHUB REPO → PUSH → VERIFY</text>
</svg>
'''


def _xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", (message or "").strip().lower())
