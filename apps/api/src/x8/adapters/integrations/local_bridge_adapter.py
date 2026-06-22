from datetime import datetime

import httpx
from pydantic import BaseModel


class LocalBridgeStatus(BaseModel):
    bridge_configured: bool
    bridge_reachable: bool
    bridge_url: str
    available_tools: list[str]
    approved_roots: list[str]
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_failure_reason: str | None = None


class PowerShellOpenResult(BaseModel):
    requested_path: str
    command: str
    launched: bool
    supported: bool
    message: str
    fallback_reason: str | None = None


class LocalBridgeAdapter:
    name = "local_bridge"
    version = "0.2.0"

    def __init__(self, url: str, token: str, approved_roots: str) -> None:
        self.url = url
        self.token = token
        self.approved_roots = [root.strip() for root in approved_roots.split(";") if root.strip()]

    @staticmethod
    def powershell_command(path: str) -> str:
        escaped = path.replace("'", "''")
        return f"powershell.exe -NoExit -Command \"Set-Location -LiteralPath '{escaped}'\""

    def status(self) -> LocalBridgeStatus:
        configured = bool(self.url and self.token)
        try:
            response = httpx.get(f"{self.url.rstrip('/')}/status", timeout=3)
            if response.status_code < 500:
                payload = response.json()
                return LocalBridgeStatus(
                    bridge_configured=True,
                    bridge_reachable=True,
                    bridge_url=self.url,
                    available_tools=list(payload.get("available_tools", [])),
                    approved_roots=list(payload.get("approved_roots", self.approved_roots)),
                    last_success_at=datetime.now(),
                )
        except Exception as exc:
            failure = str(exc)
        else:
            failure = f"Bridge returned HTTP {response.status_code}"
        return LocalBridgeStatus(
            bridge_configured=configured,
            bridge_reachable=False,
            bridge_url=self.url,
            available_tools=[],
            approved_roots=self.approved_roots,
            last_failure_at=datetime.now(),
            last_failure_reason=failure if configured else "Local bridge token not configured",
        )

    def open_powershell(self, path: str) -> PowerShellOpenResult:
        command = self.powershell_command(path)
        try:
            response = httpx.post(f"{self.url.rstrip('/')}/tools/open-powershell", json={"path": path}, timeout=5)
            if response.status_code < 500:
                return PowerShellOpenResult(**response.json())
            failure = f"Bridge returned HTTP {response.status_code}"
        except Exception as exc:
            failure = str(exc)
        return PowerShellOpenResult(
            requested_path=path,
            command=command,
            launched=False,
            supported=False,
            message="PowerShell could not be launched through the local bridge.",
            fallback_reason=failure,
        )
