import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from x8.managers.github_ops_manager import GitHubOpsManager
from x8.managers.workspace_manager import FileEntry, FileRead, WorkspaceManager


class IDEPermission(BaseModel):
    action: str
    allowed: bool
    blocked: bool = False
    approval_required: bool = False
    reason: str
    scope: str = "workspace"


class IDEActivity(BaseModel):
    action_type: str
    scope: str
    approval_required: bool
    status: str
    files_touched: list[str] = Field(default_factory=list)
    command: str = ""
    proof: str = ""
    fallback: str = ""


class IDECommandProposal(BaseModel):
    command: str
    category: str
    allowed: bool
    blocked: bool
    approval_required: bool
    reason: str
    scope: str = "workspace"


class IDECommandResult(BaseModel):
    command: str
    category: str
    status: str
    exit_code: int | None = None
    output: str = ""
    approval_required: bool = False
    blocked_reason: str = ""


class IDERollbackProposal(BaseModel):
    action: str
    command: str
    allowed: bool
    approval_required: bool
    reason: str
    preview_output: str = ""


class IDESummary(BaseModel):
    workspace_root: str
    files: list[FileEntry]
    selected_file: FileRead | None = None
    git_status: dict[str, object]
    checkpoint: dict[str, object]
    test_commands: list[str]
    permissions: list[IDEPermission]
    activity: list[IDEActivity]


TEST_COMMANDS = [
    "docker compose -f compose.yaml run --rm --build architecture-guard",
    "docker compose -f compose.yaml run --rm --build api-tests",
    "docker compose -f compose.yaml run --rm --build web-tests",
    "docker compose -f compose.yaml run --rm --build e2e-fast-tests",
    "docker compose -f compose.yaml run --rm --build e2e-brain-tests",
    "docker compose -f compose.yaml run --rm --build e2e-self-build-tests",
    "docker compose -f compose.yaml run --rm --build e2e-tests",
]

READONLY_COMMANDS = {
    "git status --short",
    "git branch --show-current",
    "git log --oneline -5",
    "git clean -fdn",
}

PROTECTED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\brm\s+-rf\b",
        r"\bformat\b",
        r"\bforce\s+push\b",
        r"\bgit\s+push\b.*\s--force\b",
        r"\bgit\s+push\b.*\s-f\b",
        r"\bdocker\s+compose\s+config\b",
        r"\bcat\b.*(\.env|id_rsa|token|secret)",
        r"\bprintenv\b",
        r"\bset\b.*(TOKEN|SECRET|PASSWORD|KEY)",
        r"\bRemove-Item\b.*(-Recurse|-Force)",
        r"\bdel\b.*\.git\b",
        r"\brmdir\b.*\.git\b",
        r"\.git",
    ]
]


class ChatIDEManager:
    def __init__(self, workspace_root: str, github_token: str = "", github_owner: str = "", github_visibility: str = "private") -> None:
        self.workspace = WorkspaceManager(workspace_root)
        self.git = GitHubOpsManager(workspace_root, github_token, github_owner, github_visibility)
        self.root = Path(workspace_root).resolve()

    def permission(self, action: str, scope: str = "workspace") -> IDEPermission:
        if action in {"read_workspace", "open_file", "propose_file_edit", "run_readonly_command", "run_test_command", "git_status"}:
            return IDEPermission(action=action, allowed=True, reason="Read/proposal action is allowed without mutation.", scope=scope)
        if action in {"apply_file_edit", "run_mutating_command", "git_commit", "git_push", "rollback"}:
            return IDEPermission(action=action, allowed=True, approval_required=True, reason="Mutation requires explicit approval.", scope=scope)
        return IDEPermission(action=action, allowed=False, blocked=True, reason="Unknown IDE action.", scope=scope)

    def summary(self, selected_path: str = "README.md") -> IDESummary:
        files = self.workspace.list_files(120)
        selected_file = None
        try:
            selected_file = self.workspace.read_file(selected_path)
        except (FileNotFoundError, ValueError):
            selected_file = None
        git_status = self.git.local_status(".")
        checkpoint = self.checkpoint()
        permissions = [self.permission(action) for action in ["read_workspace", "open_file", "propose_file_edit", "apply_file_edit", "run_test_command", "git_status", "git_commit", "git_push", "rollback"]]
        activity = [
            IDEActivity(action_type="read_workspace", scope="workspace", approval_required=False, status="allowed", proof=f"{len(files)} file entries loaded."),
            IDEActivity(action_type="git_status", scope="repository", approval_required=False, status="allowed", proof=f"Branch {git_status.get('branch', '')} inspected."),
        ]
        return IDESummary(workspace_root=str(self.root), files=files, selected_file=selected_file, git_status=git_status, checkpoint=checkpoint, test_commands=TEST_COMMANDS, permissions=permissions, activity=activity)

    def open_file(self, path: str) -> FileRead:
        return self.workspace.read_file(path)

    def propose_command(self, command: str) -> IDECommandProposal:
        clean = " ".join(command.strip().split())
        if self._is_protected(clean):
            return IDECommandProposal(command=clean, category="destructive/protected", allowed=False, blocked=True, approval_required=True, reason="Protected or secret-revealing command is blocked by default.")
        if clean in TEST_COMMANDS:
            return IDECommandProposal(command=clean, category="validation/test", allowed=True, blocked=False, approval_required=False, reason="Known local validation command is allowed.")
        if clean in READONLY_COMMANDS:
            return IDECommandProposal(command=clean, category="read-only safe", allowed=True, blocked=False, approval_required=False, reason="Known read-only command is allowed.")
        if clean.startswith("git commit"):
            return IDECommandProposal(command=clean, category="write/mutation", allowed=True, blocked=False, approval_required=True, reason="Commit requires explicit approval and local review.")
        return IDECommandProposal(command=clean, category="write/mutation", allowed=False, blocked=True, approval_required=True, reason="Command is not on the Chat IDE allowlist.")

    def run_command(self, command: str, approved: bool = False) -> IDECommandResult:
        proposal = self.propose_command(command)
        if proposal.blocked:
            return IDECommandResult(command=proposal.command, category=proposal.category, status="blocked", approval_required=proposal.approval_required, blocked_reason=proposal.reason)
        if proposal.approval_required and not approved:
            return IDECommandResult(command=proposal.command, category=proposal.category, status="approval_required", approval_required=True, blocked_reason=proposal.reason)
        result = subprocess.run(proposal.command.split(), cwd=self.root, capture_output=True, text=True, timeout=180, check=False)
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
        return IDECommandResult(command=proposal.command, category=proposal.category, status="passed" if result.returncode == 0 else "failed", exit_code=result.returncode, output=output[:6000])

    def git_status(self) -> dict[str, object]:
        status = self.git.local_status(".")
        status["recent_commits"] = self._git_lines(["log", "--oneline", "-5"])
        return status

    def checkpoint(self) -> dict[str, object]:
        status = self.git.local_status(".")
        return {
            "branch": status.get("branch", ""),
            "head": status.get("last_commit", {}),
            "working_tree_dirty": status.get("dirty", False),
            "changed_files": status.get("changed_files", []),
            "rollback_guidance": ["Review diff before discard.", "Preview untracked cleanup with git clean -fdn.", "Reset requires explicit approval."],
        }

    def rollback_proposal(self, action: str) -> IDERollbackProposal:
        if action == "preview_untracked_cleanup":
            result = subprocess.run(["git", "clean", "-fdn"], cwd=self.root, capture_output=True, text=True, timeout=30, check=False)
            return IDERollbackProposal(action=action, command="git clean -fdn", allowed=True, approval_required=False, reason="Preview only; no files deleted.", preview_output=result.stdout.strip())
        commands = {
            "discard_working_tree": "git restore .",
            "reset_to_origin_main": "git reset --hard origin/main",
        }
        command = commands.get(action, "")
        if not command:
            return IDERollbackProposal(action=action, command="", allowed=False, approval_required=True, reason="Unknown rollback action.")
        return IDERollbackProposal(action=action, command=command, allowed=True, approval_required=True, reason="Rollback is destructive and requires explicit approval.")

    def _git_lines(self, args: list[str]) -> list[str]:
        result = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, timeout=30, check=False)
        return [line for line in result.stdout.splitlines() if line.strip()]

    def _is_protected(self, command: str) -> bool:
        return any(pattern.search(command) for pattern in PROTECTED_PATTERNS)
