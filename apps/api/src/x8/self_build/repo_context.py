import os
import subprocess
from pathlib import Path

from x8.self_build.contracts import FileReadResult, RepoContextSnapshot

ALLOWED_ROOTS = ("apps", "docs", "config", "docker", "e2e", "knowledge", "scripts")
ALLOWED_FILES = {"README.md", "compose.yaml", ".env.example", ".gitignore"}
BLOCKED_PARTS = {"runtime", "imports", "node_modules", "dist", "build", "coverage", "playwright-report", "test-results", "__pycache__", "attachments", "logs", ".git"}
BLOCKED_SUFFIXES = {".pyc", ".log"}


class RepoContextReader:
    def __init__(self, workspace_root: str = "/workspace") -> None:
        self.root = Path(workspace_root).resolve()

    def allowed_paths(self) -> list[str]:
        return [*ALLOWED_ROOTS, *sorted(ALLOWED_FILES)]

    def blocked_paths(self) -> list[str]:
        return [*sorted(BLOCKED_PARTS), "*.pyc", "*.log", ".env", ".env.*"]

    def is_allowed(self, relative_path: str) -> bool:
        path = Path(relative_path)
        parts = set(path.parts)
        if relative_path == ".env" or relative_path.startswith(".env."):
            return False
        if parts & BLOCKED_PARTS or path.suffix in BLOCKED_SUFFIXES:
            return False
        if path.parts and path.parts[0] in ALLOWED_ROOTS:
            return True
        return relative_path in ALLOWED_FILES

    def resolve(self, relative_path: str) -> Path:
        if not self.is_allowed(relative_path):
            raise ValueError(f"Blocked self-build path: {relative_path}")
        target = (self.root / relative_path).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("Path escapes workspace root.")
        return target

    def list_tree(self, limit: int = 250) -> list[str]:
        values: list[str] = []
        for root_dir, dirs, files in os.walk(self.root):
            rel_root = Path(root_dir).relative_to(self.root)
            dirs[:] = [name for name in dirs if self.is_allowed(str(rel_root / name))]
            for name in files:
                rel = str(rel_root / name).replace("\\", "/")
                if self.is_allowed(rel):
                    values.append(rel)
                if len(values) >= limit:
                    return values
        return sorted(values)

    def read_file(self, relative_path: str, max_chars: int = 100000) -> FileReadResult:
        try:
            target = self.resolve(relative_path)
        except ValueError as exc:
            return FileReadResult(path=relative_path, blocked=True, status="blocked", limitations=[str(exc)])
        if not target.exists() or not target.is_file():
            return FileReadResult(path=relative_path, blocked=True, status="missing", limitations=["File is missing or not a regular file."])
        text = target.read_text(encoding="utf-8", errors="ignore")
        return FileReadResult(path=relative_path, content=text[:max_chars], size_bytes=target.stat().st_size, status="read", limitations=["truncated"] if len(text) > max_chars else [])

    def snapshot(self, files_to_read: list[str] | None = None) -> RepoContextSnapshot:
        files_to_read = ["README.md"] if files_to_read is None else files_to_read
        read_results = [self.read_file(path) for path in files_to_read]
        return RepoContextSnapshot(
            status="completed",
            files_listed=self.list_tree(),
            files_read=[item.path for item in read_results if not item.blocked],
            git_status=self._git(["status", "--short"]),
            git_diff_summary=self._git(["diff", "--stat"]),
        )

    def _git(self, args: list[str]) -> str:
        try:
            result = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, timeout=10, check=False)
            return (result.stdout or result.stderr)[:4000]
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"git unavailable: {exc}"
