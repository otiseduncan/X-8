import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from x8.contracts.receipts import Receipt


class DockerPreset(BaseModel):
    preset_name: str
    allowed_command: list[str]
    timeout_seconds: int
    risk_level: str
    approval_required: bool
    output_capture_policy: str = "summarize"


PRESETS = {
    "compose_config": DockerPreset(preset_name="compose_config", allowed_command=["docker", "compose", "config"], timeout_seconds=60, risk_level="safe_read", approval_required=False),
    "service_status": DockerPreset(preset_name="service_status", allowed_command=["docker", "compose", "ps"], timeout_seconds=30, risk_level="safe_read", approval_required=False),
    "service_logs": DockerPreset(preset_name="service_logs", allowed_command=["docker", "compose", "logs", "--tail=80"], timeout_seconds=30, risk_level="safe_read", approval_required=False),
    "architecture_guard": DockerPreset(preset_name="architecture_guard", allowed_command=["docker", "compose", "run", "--rm", "architecture-guard"], timeout_seconds=120, risk_level="low_change", approval_required=True),
    "api_tests": DockerPreset(preset_name="api_tests", allowed_command=["docker", "compose", "run", "--rm", "api-tests"], timeout_seconds=180, risk_level="low_change", approval_required=True),
    "web_tests": DockerPreset(preset_name="web_tests", allowed_command=["docker", "compose", "run", "--rm", "web-tests"], timeout_seconds=180, risk_level="low_change", approval_required=True),
    "e2e_tests": DockerPreset(preset_name="e2e_tests", allowed_command=["docker", "compose", "run", "--rm", "e2e-tests"], timeout_seconds=240, risk_level="low_change", approval_required=True),
    "comfyui_status": DockerPreset(preset_name="comfyui_status", allowed_command=["docker", "compose", "ps", "x8-comfyui"], timeout_seconds=30, risk_level="safe_read", approval_required=False),
    "searxng_status": DockerPreset(preset_name="searxng_status", allowed_command=["docker", "compose", "ps", "x8-searxng"], timeout_seconds=30, risk_level="safe_read", approval_required=False),
    "runtime_health": DockerPreset(preset_name="runtime_health", allowed_command=["docker", "compose", "ps"], timeout_seconds=30, risk_level="safe_read", approval_required=False),
}


class DockerCommandResult(BaseModel):
    command_id: str
    preset_name: str
    started_at: datetime
    completed_at: datetime
    exit_code: int | None
    stdout_summary: str
    stderr_summary: str
    full_output_reference: str
    receipt_id: str
    status: str
    limitations: list[str]


class DockerCommandPresetManager:
    name = "docker_command_presets"
    version = "0.1.0"

    def __init__(self, working_directory: str = "/workspace") -> None:
        self.working_directory = Path(working_directory)

    def presets(self) -> list[str]:
        return sorted(PRESETS)

    def preset_defs(self) -> list[DockerPreset]:
        return [PRESETS[name] for name in self.presets()]

    def run_preset(self, preset_name: str, approved: bool = False) -> DockerCommandResult:
        started = datetime.now(timezone.utc)
        preset = PRESETS[preset_name]
        receipt = Receipt(action=f"docker.preset.{preset_name}", status="started", summary="Controlled Docker preset requested.")
        if preset.approval_required and not approved:
            return self._result(preset, started, None, "", "Click approval required.", receipt.id, "pending_click", ["Preset requires click approval."])
        if not shutil.which("docker"):
            return self._result(preset, started, None, "", "Docker CLI unavailable in runtime.", receipt.id, "not_run_environment_unavailable", ["Docker CLI not found."])
        try:
            completed = subprocess.run(
                preset.allowed_command,
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                timeout=preset.timeout_seconds,
                check=False,
            )
        except Exception as exc:
            return self._result(preset, started, None, "", str(exc), receipt.id, "failed", [str(exc)])
        status = "passed" if completed.returncode == 0 else "failed"
        return self._result(preset, started, completed.returncode, completed.stdout, completed.stderr, receipt.id, status, [])

    def _result(self, preset: DockerPreset, started: datetime, exit_code: int | None, stdout: str, stderr: str, receipt_id: str, status: str, limitations: list[str]) -> DockerCommandResult:
        return DockerCommandResult(
            command_id=f"cmd_{uuid4().hex[:10]}",
            preset_name=preset.preset_name,
            started_at=started,
            completed_at=datetime.now(timezone.utc),
            exit_code=exit_code,
            stdout_summary=stdout[-1200:],
            stderr_summary=stderr[-1200:],
            full_output_reference="captured_inline_summary",
            receipt_id=receipt_id,
            status=status,
            limitations=limitations,
        )
