from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel


class LocalDriveInfo(BaseModel):
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int


class LocalSystemStatus(BaseModel):
    os_name: str
    os_release: str
    machine: str
    python_version: str
    cpu_count: int
    workspace_root: str
    approved_roots: list[str]
    drives: list[LocalDriveInfo]
    docker_cli_available: bool
    docker_engine_reachable: bool
    docker_engine_version: str | None = None
    docker_failure_reason: str | None = None


class LocalSystemAdapter:
    def __init__(self, workspace_root: str, approved_roots: str) -> None:
        self.workspace_root = workspace_root
        self.approved_roots = [root.strip() for root in approved_roots.split(";") if root.strip()]

    def status(self) -> LocalSystemStatus:
        drives = self._drives()
        docker_cli_available, docker_engine_reachable, docker_engine_version, docker_failure_reason = self._docker_status()
        return LocalSystemStatus(
            os_name=platform.system(),
            os_release=platform.release(),
            machine=platform.machine(),
            python_version=platform.python_version(),
            cpu_count=os.cpu_count() or 0,
            workspace_root=self.workspace_root,
            approved_roots=self.approved_roots,
            drives=drives,
            docker_cli_available=docker_cli_available,
            docker_engine_reachable=docker_engine_reachable,
            docker_engine_version=docker_engine_version,
            docker_failure_reason=docker_failure_reason,
        )

    def _drives(self) -> list[LocalDriveInfo]:
        candidates = [self.workspace_root, *self.approved_roots]
        seen: set[str] = set()
        result: list[LocalDriveInfo] = []
        for raw in candidates:
            if not raw:
                continue
            path = Path(raw)
            try:
                resolved = str(path.resolve())
            except Exception:
                resolved = str(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                usage = shutil.disk_usage(resolved)
            except OSError:
                continue
            result.append(
                LocalDriveInfo(
                    path=resolved,
                    total_bytes=usage.total,
                    used_bytes=usage.used,
                    free_bytes=usage.free,
                )
            )
        return result

    def _docker_status(self) -> tuple[bool, bool, str | None, str | None]:
        if shutil.which("docker") is None:
            return False, False, None, "Docker CLI is not installed or not on PATH."
        try:
            response = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
        except Exception as exc:
            return True, False, None, str(exc)
        if response.returncode == 0:
            return True, True, response.stdout.strip() or None, None
        reason = (response.stderr or response.stdout or "Docker engine unreachable.").strip()
        return True, False, None, reason
