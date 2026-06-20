import difflib
import hashlib
from datetime import datetime, timezone

from x8.self_build.contracts import PatchFileChange, PatchProposal, SelfBuildPlan, SelfBuildTask
from x8.self_build.repo_context import RepoContextReader
from x8.self_build.validation import PatchValidationManager

SMOKE_PROOF_FILE = "runtime/self_build_smoke/approved_apply_proof.md"
DESTRUCTIVE_PROMPT_PHRASES = ("delete", "remove", "wipe", "erase", "destroy", "drop table", "rm -rf", "credential", "token", "secret", "password")


class PatchProposalManager:
    def __init__(self, reader: RepoContextReader) -> None:
        self.reader = reader
        self.validation = PatchValidationManager(reader)

    def create(self, task: SelfBuildTask, plan: SelfBuildPlan) -> PatchProposal:
        changes: list[PatchFileChange] = []
        if self._has_destructive_prompt(task.request.user_prompt):
            validation = self.validation.validate(changes)
            validation.reasons.append("Destructive or secret-related self-build request is blocked.")
            validation.passed = False
            validation.status = "failed"
            return PatchProposal(task_id=task.task_id, plan_id=plan.plan_id, changes=changes, patch_hash=self.hash_changes(changes), validation=validation, status="blocked")
        if plan.task_type == "unknown_safe":
            validation = self.validation.validate(changes)
            return PatchProposal(task_id=task.task_id, plan_id=plan.plan_id, changes=changes, patch_hash=self.hash_changes(changes), validation=validation, status="blocked")
        for path in plan.modified_files:
            before = self.reader.read_file(path)
            if before.blocked:
                continue
            after = self._proposed_content(path, before.content, task.request.user_prompt, plan.task_type)
            diff = "".join(difflib.unified_diff(before.content.splitlines(True), after.splitlines(True), fromfile=f"a/{path}", tofile=f"b/{path}"))
            if after == before.content:
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
        self._add_task_specific_validation(plan, task, changes, validation)
        return PatchProposal(task_id=task.task_id, plan_id=plan.plan_id, changes=changes, patch_hash=patch_hash, validation=validation, status="proposed" if validation.passed else "blocked")

    def hash_changes(self, changes: list[PatchFileChange]) -> str:
        raw = "\n".join(f"{item.file_path}:{item.before_hash}:{item.after_hash}:{item.unified_diff}:{item.proposed_content}" for item in changes)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _hash_text(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _proposed_content(self, path: str, before: str, prompt: str, task_type: str) -> str:
        lower_path = path.lower()
        lower_prompt = prompt.lower()
        if path.replace("\\", "/") == SMOKE_PROOF_FILE and self._asks_for_validation_note(lower_prompt):
            return self._append_validation_note(before, "self-build approved apply proof")
        if task_type == "docs_only" and lower_path.startswith("docs/") and lower_path.endswith(".md") and self._asks_for_validation_note(lower_prompt):
            return self._append_validation_note(before, "bounded docs self-build proof")
        if task_type == "ui_feature" and "trust status" in lower_prompt:
            if lower_path == "apps/web/src/services/apiclient.ts":
                return self._add_trust_status_client(before)
            if lower_path == "apps/web/src/app/app.tsx":
                return self._add_trust_status_card(before)
        if task_type == "docs_only" and lower_path == "readme.md" and "self-build mode" not in before.lower():
            section = "\n\n## Self-Build Mode\n\nXV8 can inspect its own repo and propose guarded patches. File changes require approval before apply.\n"
            return before.rstrip() + section + "\n"
        if task_type == "docs_only" and lower_path == "readme.md" and "validation smoke note" in lower_prompt and "XV8 validation smoke note" not in before:
            section = "\n\n## XV8 Validation Smoke Note\n\nThis proposed docs-only note validates the self-build approval flow without applying changes automatically.\n"
            return before.rstrip() + section + "\n"
        if task_type == "ui_feature" and lower_path.startswith("apps/web/src/"):
            return self._append_release_note(before, "UI feature proposal placeholder for a bounded cockpit improvement.")
        if task_type == "api_feature" and lower_path.startswith("apps/api/src/"):
            return self._append_release_note(before, "API feature proposal placeholder for a bounded route or manager improvement.")
        if task_type == "api_feature" and lower_path.startswith("apps/api/tests/"):
            return self._append_test_placeholder(before, "api_feature")
        if task_type == "test_only" and lower_path.startswith("apps/api/tests/"):
            return self._append_test_placeholder(before, "test_only")
        if task_type == "config_change" and lower_path == ".env.example" and "X8_RELEASE_SAFE_CONFIG_NOTE" not in before:
            return before.rstrip() + "\nX8_RELEASE_SAFE_CONFIG_NOTE=proposal_only\n"
        if task_type == "repair_patch":
            return self._append_release_note(before, "Repair patch proposal placeholder for a bounded fix.")
        if task_type == "project_builder_feature":
            if lower_path.startswith("apps/api/tests/"):
                return self._append_test_placeholder(before, "project_builder_feature")
            return self._append_release_note(before, "Project Builder proposal placeholder for a sandboxed build/write feature.")
        return before

    def _asks_for_validation_note(self, lower_prompt: str) -> bool:
        return any(phrase in lower_prompt for phrase in ("validation note", "timestamped", "proof note", "smoke note", "checklist line"))

    def _has_destructive_prompt(self, prompt: str) -> bool:
        lower_prompt = prompt.lower()
        return any(phrase in lower_prompt for phrase in DESTRUCTIVE_PROMPT_PHRASES)

    def _append_validation_note(self, before: str, label: str) -> str:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        note = f"- {stamp} - {label}."
        return before.rstrip() + "\n" + note + "\n"

    def _append_release_note(self, before: str, label: str) -> str:
        marker = f"# XV8 self-build proposal: {label}"
        if marker in before:
            return before
        return before.rstrip() + f"\n\n{marker}\n"

    def _append_test_placeholder(self, before: str, label: str) -> str:
        name = label.replace("-", "_")
        marker = f"def test_self_build_{name}_proposal_placeholder() -> None:"
        if marker in before:
            return before
        return before.rstrip() + f"\n\n\ndef test_self_build_{name}_proposal_placeholder() -> None:\n    assert True\n"

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
        if "setSelfBuildTrustStatus(response.data" not in after:
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
        if "Self-build trust gate" not in after:
            panel_anchor = '          <Panel icon={<Activity />} title="Model + Runtime">\n'
            panel = """          <Panel icon={<ShieldCheck />} title="Self-build trust gate">
            <div className="list dense selfBuildTrustCard" style={{ borderColor: '#22d3ee' }}>
              <div className="row split"><strong>Self-build trust gate</strong><StatusPill label={selfBuildTrustSummary === 'checking' ? 'loading' : selfBuildTrustSummary} status={selfBuildTrustSummary} /></div>
              {selfBuildTrustSummary === 'unavailable' && <div className="row"><strong>Status</strong><span>Trust status unavailable. Check the API route.</span></div>}
              <div className="row split"><strong>Approval required</strong><span>{String(selfBuildTrustStatus.approval_required ?? 'unknown')}</span></div>
              <div className="row split"><strong>Hash approval required</strong><span>{String(selfBuildTrustStatus.approval_hash_required ?? 'unknown')}</span></div>
              <div className="row split"><strong>Writes without approval</strong><span>{String(selfBuildTrustStatus.writes_without_approval ?? 'unknown')}</span></div>
              <div className="row split"><strong>Commit default</strong><span>{String(selfBuildTrustStatus.commit_allowed_by_default ?? 'unknown')}</span></div>
              <div className="row split"><strong>Push default</strong><span>{String(selfBuildTrustStatus.push_allowed_by_default ?? 'unknown')}</span></div>
              <div className="row split"><strong>Validation preset count</strong><span>{Array.isArray(selfBuildTrustStatus.validation_presets) ? selfBuildTrustStatus.validation_presets.length : 'unknown'}</span></div>
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

    def _add_task_specific_validation(self, plan: SelfBuildPlan, task: SelfBuildTask, changes: list[PatchFileChange], validation) -> None:
        lower_prompt = task.request.user_prompt.lower()
        if plan.task_type == "ui_feature" and "trust status" in lower_prompt:
            app_changes = [change for change in changes if change.file_path == "apps/web/src/app/App.tsx"]
            has_visible_render = any("Self-build trust gate" in change.proposed_content and "Validation preset count" in change.proposed_content for change in app_changes)
            if not has_visible_render:
                validation.reasons.append("UI feature proposal did not generate visible Self-build trust gate JSX.")
            if validation.reasons:
                validation.passed = False
                validation.status = "failed"
