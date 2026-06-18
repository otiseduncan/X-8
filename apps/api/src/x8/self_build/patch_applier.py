import hashlib
from pathlib import Path

from x8.self_build.contracts import PatchApplyRequest, PatchApplyResult, PatchProposal
from x8.self_build.repo_context import RepoContextReader


class SafePatchApplier:
    def __init__(self, reader: RepoContextReader, backup_root: str = "/workspace/runtime/self-build-backups") -> None:
        self.reader = reader
        self.backup_root = Path(backup_root)

    def apply(self, proposal: PatchProposal, request: PatchApplyRequest, approval_hash: str) -> PatchApplyResult:
        if not request.approved:
            return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason="Patch apply denied or not approved.")
        if request.patch_hash != proposal.patch_hash or approval_hash != proposal.patch_hash:
            return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason="Patch hash mismatch invalidated approval.")
        if not proposal.validation.passed:
            return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason="Patch validation failed.")
        changed: list[str] = []
        backups: list[str] = []
        for change in proposal.changes:
            try:
                target = self.reader.resolve(change.file_path)
            except ValueError as exc:
                return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason=str(exc), changed_files=changed, backup_paths=backups)
            before = target.read_text(encoding="utf-8", errors="ignore") if target.exists() else ""
            after = self._apply_unified_append(before, change.unified_diff)
            backup = self._backup_path(change.file_path, before)
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(before, encoding="utf-8")
            target.write_text(after, encoding="utf-8")
            changed.append(change.file_path)
            backups.append(str(backup))
        return PatchApplyResult(patch_id=proposal.patch_id, applied=True, status="applied", changed_files=changed, backup_paths=backups, reason="Patch applied after exact approval hash match.")

    def _backup_path(self, file_path: str, content: str) -> Path:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        safe = file_path.replace("/", "_").replace("\\", "_")
        return self.backup_root / f"{safe}.{digest}.bak"

    def _apply_unified_append(self, before: str, diff: str) -> str:
        added = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
        if not added:
            return before
        addition = "\n".join(added).rstrip()
        if addition and addition not in before:
            return before.rstrip() + "\n" + addition + "\n"
        return before
