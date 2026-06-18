import hashlib
from pathlib import Path

from x8.self_build.contracts import PatchApplyRequest, PatchApplyResult, PatchFileChange, PatchProposal
from x8.self_build.repo_context import RepoContextReader


class SafePatchApplier:
    def __init__(self, reader: RepoContextReader, backup_root: str = "/workspace/runtime/self-build-backups") -> None:
        self.reader = reader
        self.backup_root = Path(backup_root)

    def apply(self, proposal: PatchProposal, request: PatchApplyRequest, approval_hash: str) -> PatchApplyResult:
        if request.patch_id != proposal.patch_id:
            return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason="Patch id mismatch invalidated approval.")
        if not request.approved:
            return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason="Patch apply denied or not approved.")
        if request.patch_hash != proposal.patch_hash or approval_hash != proposal.patch_hash:
            return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason="Patch hash mismatch invalidated approval.")
        if not proposal.validation.passed:
            return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason="Patch validation failed.")
        changed: list[str] = []
        backups: list[str] = []
        originals: list[tuple[Path, str]] = []
        prepared: list[tuple[PatchFileChange, Path, str]] = []
        for change in proposal.changes:
            try:
                target = self.reader.resolve(change.file_path)
            except ValueError as exc:
                return PatchApplyResult(patch_id=proposal.patch_id, applied=False, status="blocked", reason=str(exc), changed_files=changed, backup_paths=backups)
            before = target.read_text(encoding="utf-8", errors="ignore") if target.exists() else ""
            before_hash = hashlib.sha256(before.encode("utf-8")).hexdigest()
            if before_hash != change.before_hash:
                return PatchApplyResult(
                    patch_id=proposal.patch_id,
                    applied=False,
                    status="blocked",
                    changed_files=changed,
                    backup_paths=backups,
                    reason=f"File changed since proposal: {change.file_path}",
                )
            after_hash = hashlib.sha256(change.proposed_content.encode("utf-8")).hexdigest()
            if after_hash != change.after_hash:
                return PatchApplyResult(
                    patch_id=proposal.patch_id,
                    applied=False,
                    status="blocked",
                    changed_files=changed,
                    backup_paths=backups,
                    reason=f"Proposed content hash mismatch: {change.file_path}",
                )
            prepared.append((change, target, before))
        for change, target, before in prepared:
            backup = self._backup_path(change.file_path, before)
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(before, encoding="utf-8")
            originals.append((target, before))
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.proposed_content, encoding="utf-8")
                changed.append(change.file_path)
                backups.append(str(backup))
            except OSError as exc:
                self._restore(originals)
                return PatchApplyResult(
                    patch_id=proposal.patch_id,
                    applied=False,
                    reverted=True,
                    status="failed_reverted",
                    changed_files=changed,
                    backup_paths=backups,
                    reason=f"Patch write failed and changed files were restored: {exc}",
                )
        return PatchApplyResult(patch_id=proposal.patch_id, applied=True, validation_passed=True, status="applied", changed_files=changed, backup_paths=backups, reason="Patch applied after exact approval hash match.")

    def _backup_path(self, file_path: str, content: str) -> Path:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        safe = file_path.replace("/", "_").replace("\\", "_")
        return self.backup_root / f"{safe}.{digest}.bak"

    def _restore(self, originals: list[tuple[Path, str]]) -> None:
        for target, content in reversed(originals):
            target.write_text(content, encoding="utf-8")
