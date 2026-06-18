from pydantic import BaseModel
import httpx
import subprocess

from x8.contracts.capability import CapabilityStatus


class GitHubStatus(BaseModel):
    status: str
    capability: CapabilityStatus
    reason: str
    owner: str
    repo: str
    default_branch: str


class GitHubAdapter:
    name = "github"
    version = "0.1.0"

    def __init__(self, token: str, owner: str, repo: str, default_branch: str) -> None:
        self.token = token
        self.owner = owner
        self.repo = repo
        self.default_branch = default_branch

    def status(self) -> GitHubStatus:
        if not self.token:
            return GitHubStatus(
                status="not_configured",
                capability=CapabilityStatus.UNAVAILABLE,
                reason="GitHub token not configured",
                owner=self.owner,
                repo=self.repo,
                default_branch=self.default_branch,
            )
        return GitHubStatus(
            status="configured",
            capability=CapabilityStatus.IMPLEMENTED,
            reason="GitHub token present; live API calls are enabled for repository endpoints.",
            owner=self.owner,
            repo=self.repo,
            default_branch=self.default_branch,
        )

    def _api_get(self, path: str) -> dict[str, object] | list[object]:
        if not self.token:
            return {"status": "not_configured", "reason": "GitHub token not configured"}
        response = httpx.get(
            f"https://api.github.com{path}",
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def authenticated_user(self) -> dict[str, object]:
        return dict(self._api_get("/user"))

    def repository_metadata(self) -> dict[str, str]:
        status = self.status()
        if not self.token:
            return {"owner": self.owner, "repo": self.repo, "default_branch": self.default_branch, "status": status.status}
        repo = self._api_get(f"/repos/{self.owner}/{self.repo}")
        return {
            "owner": str(repo.get("owner", {}).get("login", self.owner)),
            "repo": str(repo.get("name", self.repo)),
            "default_branch": str(repo.get("default_branch", self.default_branch)),
            "status": "configured",
        }

    def branches(self) -> list[str]:
        if not self.token:
            return [self.default_branch]
        data = self._api_get(f"/repos/{self.owner}/{self.repo}/branches")
        return [str(item.get("name")) for item in data if isinstance(item, dict)]

    def commits(self) -> list[dict[str, str]]:
        if not self.token:
            return [{"sha": "not_configured", "message": "Recent commits require live GitHub credentials."}]
        data = self._api_get(f"/repos/{self.owner}/{self.repo}/commits?per_page=5")
        return [
            {"sha": str(item.get("sha", ""))[:12], "message": str(item.get("commit", {}).get("message", "")).splitlines()[0]}
            for item in data
            if isinstance(item, dict)
        ]

    def file_fetch(self, path: str, ref: str | None = None) -> dict[str, str]:
        if not self.token:
            return {"status": "not_configured", "reason": "GitHub token not configured", "path": path}
        suffix = f"?ref={ref}" if ref else ""
        data = self._api_get(f"/repos/{self.owner}/{self.repo}/contents/{path}{suffix}")
        return {"path": path, "name": str(data.get("name", path)), "download_url": str(data.get("download_url", ""))}

    def changed_files(self, workspace_root: str = "/workspace") -> list[str]:
        try:
            result = subprocess.run(["git", "status", "--short"], cwd=workspace_root, capture_output=True, text=True, timeout=10, check=False)
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            return []

    def pull_request_readiness(self, workspace_root: str = "/workspace") -> dict[str, object]:
        changed = self.changed_files(workspace_root)
        return {"ready": bool(self.token), "changed_files": changed, "push_enabled": False, "reason": "Push and PR creation require separate explicit approval."}

    def commit_proposal(self, message: str, workspace_root: str = "/workspace") -> dict[str, object]:
        return {"message": message, "changed_files": self.changed_files(workspace_root), "mutated": False, "requires_approval": True}
