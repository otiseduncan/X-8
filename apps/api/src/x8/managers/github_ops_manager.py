import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx


class GitHubOpsManager:
    def __init__(self, workspace_root: str, token: str = "", owner: str = "", default_visibility: str = "private") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.token = token
        self.owner = owner
        self.default_visibility = default_visibility if default_visibility in {"private", "public"} else "private"

    def auth_status(self) -> dict[str, object]:
        return {
            "token_configured": bool(self.token),
            "owner_configured": bool(self.owner),
            "owner": self.owner,
            "default_visibility": self.default_visibility,
        }

    def local_status(self, path: str = ".") -> dict[str, object]:
        cwd = self._resolve_path(path)
        is_repo = self._git(cwd, ["rev-parse", "--is-inside-work-tree"]).stdout.strip() == "true"
        if not is_repo:
            return {"is_repo": False, "branch": "", "remote_origin_url": "", "dirty": False, "changed_files": [], "last_commit": {}, "ahead": None, "behind": None}
        branch = self._git(cwd, ["branch", "--show-current"]).stdout.strip()
        remote = self._sanitize_remote(self._git(cwd, ["remote", "get-url", "origin"]).stdout.strip())
        changed = [line.strip() for line in self._git(cwd, ["status", "--short"]).stdout.splitlines() if line.strip()]
        last = self._git(cwd, ["log", "-1", "--pretty=%H%x00%s"]).stdout.strip().split("\x00", 1)
        ahead, behind = self._ahead_behind(cwd)
        return {
            "is_repo": True,
            "branch": branch,
            "remote_origin_url": remote,
            "dirty": bool(changed),
            "changed_files": changed,
            "last_commit": {"sha": last[0] if last else "", "message": last[1] if len(last) > 1 else ""},
            "ahead": ahead,
            "behind": behind,
        }

    def push_preview(self, path: str = ".") -> dict[str, object]:
        status = self.local_status(path)
        cwd = self._resolve_path(path)
        branch = str(status.get("branch") or "")
        commits = []
        if branch:
            result = self._git(cwd, ["log", "--oneline", f"origin/{branch}..HEAD"])
            commits = [line for line in result.stdout.splitlines() if line.strip()]
        return {"branch": branch, "remote": status.get("remote_origin_url", ""), "commits_to_push": commits, "dirty": status.get("dirty", False), "allowed_after_approval": bool(status.get("is_repo") and status.get("remote_origin_url"))}

    def pull_preview(self, path: str = ".") -> dict[str, object]:
        status = self.local_status(path)
        return {"branch": status.get("branch", ""), "remote": status.get("remote_origin_url", ""), "dirty": status.get("dirty", False), "allowed_after_approval": bool(status.get("is_repo") and status.get("remote_origin_url"))}

    def init_repo(self, path: str = ".", approved: bool = False) -> dict[str, object]:
        if not approved:
            return self._blocked("Approval required before git init.")
        cwd = self._resolve_path(path)
        result = self._git(cwd, ["init"])
        return {"status": "applied" if result.returncode == 0 else "blocked", "reason": result.stdout.strip() or result.stderr.strip(), "changed_files": []}

    def connect_remote(self, remote_url: str, path: str = ".", approved: bool = False) -> dict[str, object]:
        if not approved:
            return self._blocked("Approval required before connecting remote.")
        if self._contains_secret_remote(remote_url):
            return self._blocked("Remote URL must not contain tokens or credentials.")
        cwd = self._resolve_path(path)
        current = self._git(cwd, ["remote", "get-url", "origin"])
        args = ["remote", "set-url", "origin", remote_url] if current.returncode == 0 else ["remote", "add", "origin", remote_url]
        result = self._git(cwd, args)
        return {"status": "applied" if result.returncode == 0 else "blocked", "reason": result.stdout.strip() or result.stderr.strip(), "remote_origin_url": self._sanitize_remote(remote_url), "changed_files": []}

    def create_repo(self, repo_name: str, visibility: str | None = None, owner: str | None = None, approved: bool = False) -> dict[str, object]:
        clean = self._sanitize_repo_name(repo_name)
        selected_visibility = visibility or self.default_visibility
        if not clean:
            return self._blocked("Invalid GitHub repository name.")
        if selected_visibility not in {"private", "public"}:
            return self._blocked("GitHub repository visibility must be private or public.")
        if not approved:
            return self._blocked("Approval required before creating GitHub repository.") | {"repo": clean, "visibility": selected_visibility}
        if not self.token:
            return self._blocked("GitHub token not configured.")
        selected_owner = owner or self.owner
        url = f"https://api.github.com/orgs/{selected_owner}/repos" if selected_owner and selected_owner != self.owner else "https://api.github.com/user/repos"
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"},
            json={"name": clean, "private": selected_visibility == "private"},
            timeout=15,
        )
        if response.status_code >= 400:
            return self._blocked(f"GitHub create repo failed: {response.status_code}")
        data = response.json()
        return {"status": "applied", "repo": clean, "visibility": selected_visibility, "html_url": str(data.get("html_url", "")), "clone_url": self._sanitize_remote(str(data.get("clone_url", ""))), "reason": "GitHub repository created."}

    def pull(self, path: str = ".", approved: bool = False) -> dict[str, object]:
        if not approved:
            return self._blocked("Approval required before git pull.")
        cwd = self._resolve_path(path)
        result = self._git(cwd, ["pull", "--ff-only"])
        return {"status": "applied" if result.returncode == 0 else "blocked", "reason": result.stdout.strip() or result.stderr.strip(), "changed_files": self.local_status(path).get("changed_files", [])}

    def push(self, path: str = ".", approved: bool = False) -> dict[str, object]:
        if not approved:
            return self._blocked("Approval required before git push.")
        cwd = self._resolve_path(path)
        branch = self.local_status(path).get("branch") or "HEAD"
        result = self._git(cwd, ["push", "origin", str(branch)])
        return {"status": "applied" if result.returncode == 0 else "blocked", "reason": result.stdout.strip() or result.stderr.strip(), "changed_files": self.local_status(path).get("changed_files", [])}

    def _resolve_path(self, path: str) -> Path:
        target = (self.workspace_root / path).resolve()
        if target != self.workspace_root and self.workspace_root not in target.parents:
            raise ValueError("GitHub operation path escapes workspace root.")
        if not target.exists() or not target.is_dir():
            raise ValueError("GitHub operation path must be an existing directory.")
        return target

    def _git(self, cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        allowed = {"rev-parse", "rev-list", "branch", "remote", "status", "log", "init", "pull", "push"}
        if not args or args[0] not in allowed:
            raise ValueError("GitHub ops only allow fixed git commands.")
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30, check=False)

    def _ahead_behind(self, cwd: Path) -> tuple[int | None, int | None]:
        result = self._git(cwd, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        upstream = result.stdout.strip()
        if result.returncode != 0 or not upstream:
            return None, None
        counts = self._git(cwd, ["rev-list", "--left-right", "--count", f"HEAD...{upstream}"]).stdout.split()
        return (int(counts[0]), int(counts[1])) if len(counts) == 2 else (None, None)

    def _sanitize_remote(self, value: str) -> str:
        parsed = urlparse(value)
        if parsed.username or parsed.password:
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))
        return value.replace(self.token, "[redacted]") if self.token else value

    def _contains_secret_remote(self, value: str) -> bool:
        parsed = urlparse(value)
        return bool(parsed.username or parsed.password or (self.token and self.token in value))

    def _sanitize_repo_name(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "-", value.strip()).strip(".-")[:100]

    def _blocked(self, reason: str) -> dict[str, object]:
        return {"status": "blocked", "reason": reason, "changed_files": []}
