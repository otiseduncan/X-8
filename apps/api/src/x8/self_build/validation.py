from x8.self_build.contracts import PatchFileChange, PatchValidationResult
from x8.self_build.repo_context import RepoContextReader

ALLOWED_PRESETS = {"architecture_guard", "api_tests", "web_tests", "e2e_tests", "web_build", "compose_config"}
BLOCKED_DIFF_PHRASES = ("subprocess.run", "shell=True", "os.system", "git push", "git commit", "print(secret", "api_key")


class PatchValidationManager:
    def __init__(self, reader: RepoContextReader) -> None:
        self.reader = reader

    def validate(self, changes: list[PatchFileChange]) -> PatchValidationResult:
        reasons: list[str] = []
        if not changes:
            reasons.append("No file changes were proposed.")
        for change in changes:
            if not self.reader.is_allowed(change.file_path):
                reasons.append(f"Blocked path: {change.file_path}")
            lower_diff = change.unified_diff.lower()
            for phrase in BLOCKED_DIFF_PHRASES:
                if phrase in lower_diff:
                    reasons.append(f"Blocked unsafe diff phrase: {phrase}")
        return PatchValidationResult(passed=not reasons, reasons=reasons, status="passed" if not reasons else "failed")

    def validate_presets(self, presets: list[str]) -> PatchValidationResult:
        blocked = [preset for preset in presets if preset not in ALLOWED_PRESETS]
        return PatchValidationResult(passed=not blocked, reasons=[f"Validation preset is not allowlisted: {preset}" for preset in blocked], status="passed" if not blocked else "failed")
