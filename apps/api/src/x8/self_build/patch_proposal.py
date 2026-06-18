import hashlib
import difflib

from x8.self_build.contracts import PatchFileChange, PatchProposal, SelfBuildPlan, SelfBuildTask
from x8.self_build.repo_context import RepoContextReader
from x8.self_build.validation import PatchValidationManager


class PatchProposalManager:
    def __init__(self, reader: RepoContextReader) -> None:
        self.reader = reader
        self.validation = PatchValidationManager(reader)

    def create(self, task: SelfBuildTask, plan: SelfBuildPlan) -> PatchProposal:
        changes: list[PatchFileChange] = []
        for path in plan.modified_files:
            before = self.reader.read_file(path)
            if before.blocked:
                continue
            after = self._proposed_content(path, before.content, task.request.user_prompt)
            diff = "".join(difflib.unified_diff(before.content.splitlines(True), after.splitlines(True), fromfile=f"a/{path}", tofile=f"b/{path}"))
            changes.append(PatchFileChange(file_path=path, before_summary=f"{path} currently has {len(before.content)} chars.", after_summary="Add guarded self-build documentation/proposed change.", unified_diff=diff, status="proposed"))
        patch_hash = self.hash_changes(changes)
        validation = self.validation.validate(changes)
        return PatchProposal(task_id=task.task_id, plan_id=plan.plan_id, changes=changes, patch_hash=patch_hash, validation=validation, status="proposed" if validation.passed else "blocked")

    def hash_changes(self, changes: list[PatchFileChange]) -> str:
        raw = "\n".join(f"{item.file_path}:{item.unified_diff}" for item in changes)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _proposed_content(self, path: str, before: str, prompt: str) -> str:
        if path.lower() == "readme.md" and "self-build mode" not in before.lower():
            section = "\n\n## Self-Build Mode\n\nXV8 can inspect its own repo and propose guarded patches. File changes require approval before apply.\n"
            return before.rstrip() + section + "\n"
        return before.rstrip() + "\n\n<!-- XV8 self-build proposed change: review before approval. -->\n"
