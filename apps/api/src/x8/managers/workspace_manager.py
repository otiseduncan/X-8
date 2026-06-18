from pathlib import Path

from pydantic import BaseModel


IGNORED = {".git", "node_modules", "dist", "coverage", "__pycache__", ".pytest_cache"}


class FileEntry(BaseModel):
    path: str
    kind: str
    size: int = 0


class FileRead(BaseModel):
    path: str
    content: str
    line_count: int


class WorkspaceManager:
    name = "workspace"
    version = "0.1.0"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def resolve_inside_root(self, rel_path: str) -> Path:
        target = (self.root / rel_path).resolve()
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
        return FileRead(path=rel_path, content=content, line_count=len(content.splitlines()))
