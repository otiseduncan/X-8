import subprocess

from x8.self_build.contracts import PatchFileChange, PatchValidationResult, SelfBuildTestRun
from x8.self_build.repo_context import RepoContextReader

ALLOWED_PRESETS = {"architecture_guard", "api_tests", "web_tests", "e2e_tests", "web_build", "compose_config"}
PRESET_COMMANDS = {
    "architecture_guard": ["docker", "compose", "run", "--rm", "architecture-guard"],
    "api_tests": ["docker", "compose", "run", "--rm", "api-tests"],
    "web_tests": ["docker", "compose", "run", "--rm", "web-tests"],
    "e2e_tests": ["docker", "compose", "run", "--rm", "e2e-tests"],
    "web_build": ["docker", "compose", "run", "--rm", "--no-deps", "x8-web", "npm", "run", "build"],
    "compose_config": ["docker", "compose", "config"],
}
BLOCKED_DIFF_PHRASES = ("subprocess.run", "shell=True", "os.system", "git push", "git commit", "print(secret", "api_key")


class PatchValidationManager:
    def __init__(self, reader: RepoContextReader) -> None:
        self.reader = reader

    def validate(self, changes: list[PatchFileChange]) -> PatchValidationResult:
        reasons: list[str] = []
        if not changes:
            reasons.append("No code changes were generated.")
        for change in changes:
            if not self.reader.is_allowed(change.file_path):
                reasons.append(f"Blocked path: {change.file_path}")
            if not change.unified_diff.strip():
                reasons.append(f"No code changes were generated for {change.file_path}: empty unified diff.")
            if change.before_hash and change.after_hash and change.before_hash == change.after_hash:
                reasons.append(f"No code changes were generated for {change.file_path}: before_hash equals after_hash.")
            current = self.reader.read_file(change.file_path)
            if not current.blocked and change.proposed_content == current.content:
                reasons.append(f"No code changes were generated for {change.file_path}: proposed content matches current file.")
            lower_diff = change.unified_diff.lower()
            for phrase in BLOCKED_DIFF_PHRASES:
                if phrase in lower_diff:
                    reasons.append(f"Blocked unsafe diff phrase: {phrase}")
        return PatchValidationResult(passed=not reasons, reasons=reasons, status="passed" if not reasons else "failed")

    def validate_presets(self, presets: list[str]) -> PatchValidationResult:
        blocked = [preset for preset in presets if preset not in ALLOWED_PRESETS]
        return PatchValidationResult(passed=not blocked, reasons=[f"Validation preset is not allowlisted: {preset}" for preset in blocked], status="passed" if not blocked else "failed")

    def preset_commands(self, presets: list[str]) -> dict[str, list[str]]:
        return {preset: PRESET_COMMANDS[preset] for preset in presets if preset in PRESET_COMMANDS}

    def run_presets(self, presets: list[str], timeout_seconds: int = 300) -> list[SelfBuildTestRun]:
        preset_validation = self.validate_presets(presets)
        if not preset_validation.passed:
            return [
                SelfBuildTestRun(
                    preset=preset,
                    ran=False,
                    passed=False,
                    command=[],
                    status="blocked",
                    output_summary="Validation preset is not allowlisted.",
                )
                for preset in presets
                if preset not in ALLOWED_PRESETS
            ]
        runs: list[SelfBuildTestRun] = []
        for preset in presets:
            command = PRESET_COMMANDS[preset]
            try:
                result = subprocess.run(command, cwd=self.reader.root, capture_output=True, text=True, timeout=timeout_seconds, check=False)
                output = "\n".join([result.stdout[-2000:], result.stderr[-2000:]]).strip()
                runs.append(
                    SelfBuildTestRun(
                        preset=preset,
                        ran=True,
                        passed=result.returncode == 0,
                        command=command,
                        exit_code=result.returncode,
                        output_summary=output,
                        status="passed" if result.returncode == 0 else "failed",
                    )
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                runs.append(SelfBuildTestRun(preset=preset, ran=True, passed=False, command=command, output_summary=str(exc), status="failed"))
        return runs
