from pathlib import Path
import re

from pydantic import BaseModel


class ProjectRoot(BaseModel):
    id: str
    name: str
    root: str
    kind: str = "workspace"
    exists: bool = True
    current: bool = False


class ProjectRegistryManager:
    """Registry of approved project roots for the native cockpit.

    This intentionally does not browse the whole host drive. Roots must come from
    the configured workspace root, X8_APPROVED_PROJECT_ROOTS, or mounted
    directories under /projects.
    """

    name = "project_registry"
    version = "0.1.0"

    def __init__(self, workspace_root: str, approved_project_roots: str = "", catalog_root: str = "/projects") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.approved_project_roots = approved_project_roots or ""
        self.catalog_root = Path(catalog_root).resolve()

    @staticmethod
    def slug(value: str) -> str:
        slugged = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
        return slugged or "project"

    def default_project(self) -> ProjectRoot:
        name = self.workspace_root.name or "X-8"
        return ProjectRoot(
            id="x8",
            name=name,
            root=str(self.workspace_root),
            kind="repo",
            exists=self.workspace_root.exists(),
            current=True,
        )

    def configured_projects(self) -> list[ProjectRoot]:
        projects: list[ProjectRoot] = []
        for raw_entry in self.approved_project_roots.split(";"):
            entry = raw_entry.strip()
            if not entry:
                continue
            parts = [part.strip() for part in entry.split("::")]
            if len(parts) >= 4:
                project_id, name, root, kind = parts[:4]
            elif len(parts) == 3:
                project_id, name, root = parts
                kind = "repo"
            elif len(parts) == 1:
                root = parts[0]
                name = Path(root).name or root
                project_id = self.slug(name)
                kind = "repo"
            else:
                continue
            resolved = Path(root).resolve()
            projects.append(
                ProjectRoot(
                    id=self.slug(project_id),
                    name=name or project_id,
                    root=str(resolved),
                    kind=kind or "repo",
                    exists=resolved.exists(),
                    current=False,
                )
            )
        return projects

    def mounted_catalog_projects(self) -> list[ProjectRoot]:
        if not self.catalog_root.exists() or not self.catalog_root.is_dir():
            return []
        projects: list[ProjectRoot] = []
        for child in sorted(self.catalog_root.iterdir(), key=lambda item: item.name.lower()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            projects.append(
                ProjectRoot(
                    id=self.slug(child.name),
                    name=child.name,
                    root=str(child.resolve()),
                    kind="mounted",
                    exists=True,
                    current=False,
                )
            )
        return projects

    def list_projects(self) -> list[ProjectRoot]:
        seen: set[str] = set()
        ordered: list[ProjectRoot] = []
        for project in [self.default_project(), *self.configured_projects(), *self.mounted_catalog_projects()]:
            if project.id in seen:
                continue
            seen.add(project.id)
            ordered.append(project)
        return ordered

    def get_project(self, project_id: str | None = None) -> ProjectRoot:
        selected = self.slug(project_id or "x8")
        for project in self.list_projects():
            if project.id == selected:
                if not project.exists:
                    raise FileNotFoundError(f"Approved project root is not mounted: {project.name}")
                project.current = True
                return project
        raise ValueError(f"Project is not approved or mounted: {project_id}")
