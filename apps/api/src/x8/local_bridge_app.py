from pathlib import Path
import platform
import subprocess

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from x8.settings import Settings

app = FastAPI(title="XV8 Local Bridge", version="0.2.0")
settings = Settings()


class PathInspectRequest(BaseModel):
    path: str


class OpenPowerShellRequest(BaseModel):
    path: str


def powershell_command(path: str) -> str:
    escaped = path.replace("'", "''")
    return f"powershell.exe -NoExit -Command \"Set-Location -LiteralPath '{escaped}'\""


def approved_roots() -> list[Path]:
    configured = [root.strip() for root in settings.approved_project_roots.split(";") if root.strip()]
    roots = configured or [settings.workspace_root]
    return [Path(root).resolve() for root in roots]


def resolve_inside_roots(raw_path: str) -> Path:
    target = Path(raw_path).resolve()
    for root in approved_roots():
        if target == root or root in target.parents:
            return target
    raise HTTPException(status_code=403, detail="Path is outside approved roots.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "x8-local-bridge"}


@app.get("/status")
def status() -> dict[str, object]:
    return {
        "bridge_configured": True,
        "bridge_reachable": True,
        "bridge_url": settings.local_bridge_url,
        "available_tools": ["roots", "tools", "inspect_path", "inspect_system", "open_powershell"],
        "approved_roots": [str(root) for root in approved_roots()],
        "host_os": platform.platform(),
        "workspace_roots": [settings.workspace_root],
    }


@app.get("/roots")
def roots() -> dict[str, list[str]]:
    return {"approved_roots": [str(root) for root in approved_roots()]}


@app.get("/tools")
def tools() -> dict[str, list[str]]:
    return {"tools": ["list approved roots", "inspect file metadata", "read file", "list directory", "host system summary", "open PowerShell at approved project root"]}


@app.post("/inspect/path")
def inspect_path(payload: PathInspectRequest) -> dict[str, object]:
    target = resolve_inside_roots(payload.path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist.")
    return {"path": str(target), "is_file": target.is_file(), "is_dir": target.is_dir(), "size": target.stat().st_size}


@app.post("/inspect/system")
def inspect_system() -> dict[str, str]:
    return {"host_os": platform.platform(), "python": platform.python_version()}


@app.post("/tools/open-powershell")
def open_powershell(payload: OpenPowerShellRequest) -> dict[str, object]:
    command = powershell_command(payload.path)
    if platform.system().lower() != "windows":
        return {
            "requested_path": payload.path,
            "command": command,
            "launched": False,
            "supported": False,
            "message": "PowerShell launch requires the local bridge to run natively on Windows, not inside a Linux Docker container.",
            "fallback_reason": f"Bridge host OS is {platform.platform()}",
        }

    target = resolve_inside_roots(payload.path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="PowerShell target folder does not exist.")

    try:
        subprocess.Popen(
            ["powershell.exe", "-NoExit", "-Command", f"Set-Location -LiteralPath '{str(target).replace("'", "''")}'"],
            cwd=str(target),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
    except Exception as exc:
        return {
            "requested_path": str(target),
            "command": command,
            "launched": False,
            "supported": True,
            "message": "PowerShell launch failed on the host bridge.",
            "fallback_reason": str(exc),
        }

    return {
        "requested_path": str(target),
        "command": command,
        "launched": True,
        "supported": True,
        "message": "PowerShell opened at the approved project root.",
        "fallback_reason": None,
    }
