import re
from pathlib import Path

from pydantic import BaseModel


IGNORED = {".git", "node_modules", "dist", "coverage", "__pycache__", ".pytest_cache"}
WINDOWS_ABSOLUTE = re.compile(r"^[a-zA-Z]:[\\/]")


class FileEntry(BaseModel):
    path: str
    kind: str
    size: int = 0


class FileRead(BaseModel):
    path: str
    content: str
    line_count: int


class FileWrite(BaseModel):
    path: str
    absolute_path: str
    sandbox_root: str
    bytes_written: int = 0
    line_count: int = 0
    mutated: bool = False
    blocked_reason: str | None = None


class WorkspaceManager:
    name = "workspace"
    version = "0.2.0"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def normalize_relative_path(self, rel_path: str) -> str:
        raw = (rel_path or "").strip()
        if not raw:
            raise ValueError("Path is required.")
        if WINDOWS_ABSOLUTE.match(raw) or raw.startswith(("/", "\\")):
            raise ValueError("Absolute paths are blocked. Use a path inside the selected sandbox/project root.")
        normalized = raw.replace("\\", "/").strip("/")
        if not normalized or normalized in {".", ".."}:
            raise ValueError("A file path inside the workspace root is required.")
        return normalized

    def resolve_inside_root(self, rel_path: str) -> Path:
        normalized = self.normalize_relative_path(rel_path)
        target = (self.root / normalized).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError("Path is outside workspace root.")
        if ".git" in target.parts:
            raise ValueError("Access to .git is blocked.")
        return target

    def list_files(self, limit: int = 250) -> list[FileEntry]:
        entries: list[FileEntry] = []
        for path in self.root.rglob("*"):
            rel = path.relative_to(self.root)
            if any(part in IGNORED for part in rel.parts):
                continue
            entries.append(FileEntry(path=str(rel), kind="directory" if path.is_dir() else "file", size=path.stat().st_size if path.is_file() else 0))
            if len(entries) >= limit:
                break
        return entries

    def search(self, query: str, limit: int = 50) -> list[FileEntry]:
        query_lower = query.lower()
        return [entry for entry in self.list_files(1000) if query_lower in entry.path.lower()][:limit]

    def read_file(self, rel_path: str, max_chars: int = 50000) -> FileRead:
        target = self.resolve_inside_root(rel_path)
        if not target.is_file():
            raise FileNotFoundError(rel_path)
        content = target.read_text(encoding="utf-8")[:max_chars]
        return FileRead(path=self.normalize_relative_path(rel_path), content=content, line_count=len(content.splitlines()))

    def write_file(self, rel_path: str, content: str, overwrite: bool = False, max_chars: int = 500000) -> FileWrite:
        normalized = self.normalize_relative_path(rel_path)
        if len(content) > max_chars:
            raise ValueError(f"File content exceeds the protected write limit of {max_chars} characters.")
        target = self.resolve_inside_root(normalized)
        if target.exists() and target.is_dir():
            raise ValueError("Write target is a directory.")
        if target.exists() and not overwrite:
            raise FileExistsError(normalized)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return FileWrite(
            path=normalized,
            absolute_path=str(target),
            sandbox_root=str(self.root),
            bytes_written=len(content.encode("utf-8")),
            line_count=len(content.splitlines()),
            mutated=True,
        )
