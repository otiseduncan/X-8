import difflib
import hashlib

from x8.self_build.contracts import PatchFileChange, PatchProposal, SelfBuildPlan, SelfBuildTask
from x8.self_build.repo_context import RepoContextReader
from x8.self_build.validation import PatchValidationManager


class PatchProposalManager:
    def __init__(self, reader: RepoContextReader) -> None:
        self.reader = reader
        self.validation = PatchValidationManager(reader)

    def create(self, task: SelfBuildTask, plan: SelfBuildPlan) -> PatchProposal:
        changes: list[PatchFileChange] = []
        if plan.task_type == "unknown_safe":
            validation = self.validation.validate(changes)
            return PatchProposal(task_id=task.task_id, plan_id=plan.plan_id, changes=changes, patch_hash=self.hash_changes(changes), validation=validation, status="blocked")
        for path in plan.modified_files:
            before = self.reader.read_file(path)
            if before.blocked:
                continue
            after = self._proposed_content(path, before.content, task.request.user_prompt, plan.task_type)
            diff = "".join(difflib.unified_diff(before.content.splitlines(True), after.splitlines(True), fromfile=f"a/{path}", tofile=f"b/{path}"))
            if after == before:
                continue
            changes.append(
                PatchFileChange(
                    file_path=path,
                    before_summary=f"{path} currently has {len(before.content)} chars.",
                    after_summary="Add guarded self-build documentation/proposed change.",
                    before_hash=self._hash_text(before.content),
                    after_hash=self._hash_text(after),
                    proposed_content=after,
                    unified_diff=diff,
                    status="proposed",
                )
            )
        patch_hash = self.hash_changes(changes)
        validation = self.validation.validate(changes)
        return PatchProposal(task_id=task.task_id, plan_id=plan.plan_id, changes=changes, patch_hash=patch_hash, validation=validation, status="proposed" if validation.passed else "blocked")

    def hash_changes(self, changes: list[PatchFileChange]) -> str:
        raw = "\n".join(f"{item.file_path}:{item.before_hash}:{item.after_hash}:{item.unified_diff}:{item.proposed_content}" for item in changes)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _hash_text(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _proposed_content(self, path: str, before: str, prompt: str, task_type: str) -> str:
        lower_path = path.lower()
        lower_prompt = prompt.lower()
        if task_type == "ui_feature" and "trust status" in lower_prompt:
            if lower_path == "apps/web/src/services/apiclient.ts":
                return self._add_trust_status_client(before)
            if lower_path == "apps/web/src/app/app.tsx":
                return self._add_trust_status_card(before)
        if task_type == "docs_only" and lower_path == "readme.md" and "self-build mode" not in before.lower():
            section = "\n\n## Self-Build Mode\n\nXV8 can inspect its own repo and propose guarded patches. File changes require approval before apply.\n"
            return before.rstrip() + section + "\n"
        return before

    def _add_trust_status_client(self, before: str) -> str:
        if "loadSelfBuildTrustStatus" in before:
            return before
        anchor = "export async function runSelfBuildPrompt(prompt: string) {\n"
        addition = """export function loadSelfBuildTrustStatus() {
  return getJson<ResultEnvelope<Record<string, unknown>>>('/api/self-build/trust-status');
}

"""
        if anchor in before:
            return before.replace(anchor, addition + anchor, 1)
        return before.rstrip() + "\n\n" + addition

    def _add_trust_status_card(self, before: str) -> str:
        after = before
        if "loadSelfBuildTrustStatus" not in after:
            after = after.replace("runSearch, runSelfBuildPrompt, scanX7Configs", "runSearch, runSelfBuildPrompt, loadSelfBuildTrustStatus, scanX7Configs", 1)
        if "selfBuildTrustStatus" not in after:
            state_anchor = "  const [memoryDetails, setMemoryDetails] = useState<Record<string, unknown>>({});\n"
            state_block = "  const [selfBuildTrustStatus, setSelfBuildTrustStatus] = useState<Record<string, unknown>>({});\n  const [selfBuildTrustSummary, setSelfBuildTrustSummary] = useState('checking');\n"
            after = after.replace(state_anchor, state_anchor + state_block, 1)
        if "loadSelfBuildTrustStatus().then" not in after:
            effect_anchor = "  useEffect(() => {\n    readFile(selectedPath)\n"
            effect_block = """  useEffect(() => {
    loadSelfBuildTrustStatus()
      .then((response) => {
        setSelfBuildTrustStatus(response.data || {});
        setSelfBuildTrustSummary(String(response.status || 'ready'));
      })
      .catch(() => setSelfBuildTrustSummary('unavailable'));
  }, []);

"""
            after = after.replace(effect_anchor, effect_block + effect_anchor, 1)
        if 'title="Self-Build Trust"' not in after:
            panel_anchor = '          <Panel icon={<Activity />} title="Model + Runtime">\n'
            panel = """          <Panel icon={<ShieldCheck />} title="Self-Build Trust">
            <div className="list dense">
              <div className="row split"><strong>Trust gate</strong><StatusPill label={selfBuildTrustSummary} status={selfBuildTrustSummary} /></div>
              <div className="row split"><strong>Approval required</strong><span>{String(selfBuildTrustStatus.approval_required ?? 'unknown')}</span></div>
              <div className="row split"><strong>Hash approval required</strong><span>{String(selfBuildTrustStatus.approval_hash_required ?? 'unknown')}</span></div>
              <div className="row split"><strong>Writes without approval</strong><span>{String(selfBuildTrustStatus.writes_without_approval ?? 'unknown')}</span></div>
              <div className="row split"><strong>Commit default</strong><span>{String(selfBuildTrustStatus.commit_allowed_by_default ?? 'unknown')}</span></div>
              <div className="row split"><strong>Push default</strong><span>{String(selfBuildTrustStatus.push_allowed_by_default ?? 'unknown')}</span></div>
              <div className="row"><strong>Validation presets</strong><span>{Array.isArray(selfBuildTrustStatus.validation_presets) ? selfBuildTrustStatus.validation_presets.join(', ') : 'unknown'}</span></div>
              <div className="row split"><strong>Allowed paths</strong><span>{Array.isArray(selfBuildTrustStatus.allowed_paths) ? selfBuildTrustStatus.allowed_paths.length : 'unknown'}</span></div>
              <div className="row split"><strong>Blocked paths</strong><span>{Array.isArray(selfBuildTrustStatus.blocked_paths) ? selfBuildTrustStatus.blocked_paths.length : 'unknown'}</span></div>
            </div>
          </Panel>
"""
            if panel_anchor in after:
                after = after.replace(panel_anchor, panel + panel_anchor, 1)
            else:
                after = after.replace('<Panel icon={<Activity />} title="Model + Runtime">', panel + '      <Panel icon={<Activity />} title="Model + Runtime">', 1)
        return after
