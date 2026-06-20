from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.settings import Settings
from x8.self_build.contracts import PatchApplyRequest, PatchFileChange, SelfBuildRequest
from x8.self_build.manager import SelfBuildManager
from x8.self_build.prompt_ingestor import BuildPromptIngestor
from x8.self_build.repo_context import RepoContextReader


def client(settings: Settings | None = None) -> TestClient:
    if settings is None:
        settings = Settings(knowledge_root="/app/knowledge", x7_import_root="/missing/x7", x6_import_root="/missing/x6")
        settings.ollama_base_url = "http://127.0.0.1:9"
        settings.default_chat_model = ""
        settings.fallback_chat_model = ""
        settings.code_model = ""
        settings.reasoning_model = ""
    return TestClient(create_app(settings))


def test_self_build_prompt_is_detected() -> None:
    assert BuildPromptIngestor().is_self_build_prompt("Self-build test. Inspect README.md and propose a patch. Do not commit.")
    assert BuildPromptIngestor().classify_intent("Show the full self-build patch proposal details before approval") == "inspect_proposal"
    assert BuildPromptIngestor().classify_intent("Self-build test. Inspect README.md and add a Self-Build Mode section. Do not commit.") == "create_proposal"
    assert BuildPromptIngestor().classify_intent("Self-build task: run a controlled proposal-only improvement. Add a small UI label or dashboard card that displays the current self-build trust status using the existing trust-status endpoint. Rules: Proposal only first. Do not write files until I approve the exact patch hash.") == "create_proposal"
    assert BuildPromptIngestor().classify_intent("Show self-build trust status.") == "trust_status"
    assert BuildPromptIngestor().classify_intent("Show latest self-build validation report.") == "validation_report"


def test_self_build_repo_context_allows_and_blocks_paths(tmp_path) -> None:
    (tmp_path / "README.md").write_text("XV8\n", encoding="utf-8")
    (tmp_path / "runtime").mkdir()
    reader = RepoContextReader(str(tmp_path))
    assert reader.read_file("README.md").status == "read"
    assert reader.read_file("runtime/secret.txt").blocked is True
    assert reader.read_file(".env").blocked is True


def create_ui_workspace(root) -> None:
    app_dir = root / "apps" / "web" / "src" / "app"
    services_dir = root / "apps" / "web" / "src" / "services"
    app_dir.mkdir(parents=True)
    services_dir.mkdir(parents=True)
    (app_dir / "App.tsx").write_text(
        """import { Activity, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { runSearch, runSelfBuildPrompt, scanX7Configs } from '../services/apiClient';

function StatusPill(props: { label: string; status: string }) {
  return <span>{props.label}</span>;
}

function Panel(props: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return <section>{props.title}{props.children}</section>;
}

const largeFrontendBody = `PADDING_MARKER`;

export function App() {
  const [memoryDetails, setMemoryDetails] = useState<Record<string, unknown>>({});
  const [selectedPath, setSelectedPath] = useState('README.md');
  useEffect(() => {
    readFile(selectedPath)
      .then((response) => setCode(response.data.content))
      .catch(() => setCode('File could not be loaded from the configured workspace root.'));
  }, [selectedPath]);
  return (
    <Panel icon={<Activity />} title="Model + Runtime">
      <div>runtime</div>
    </Panel>
  );
}
""",
        encoding="utf-8",
    )
    app_fixture = app_dir / "App.tsx"
    app_fixture.write_text(app_fixture.read_text(encoding="utf-8").replace("PADDING_MARKER", "x" * 22000), encoding="utf-8")
    (services_dir / "apiClient.ts").write_text(
        """import type { ResultEnvelope } from '../types/contracts';

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Request failed: ${path}`);
  return response.json();
}

export async function runSelfBuildPrompt(prompt: string) {
  const response = await fetch('/api/self-build/prompt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt })
  });
  if (!response.ok) throw new Error('Self-build prompt failed');
  return response.json();
}
""",
        encoding="utf-8",
    )


def create_self_build_smoke_workspace(root) -> None:
    target = root / "runtime" / "self_build_smoke"
    target.mkdir(parents=True)
    (target / "approved_apply_proof.md").write_text(
        "# Self-Build Approved Apply Proof\n\nThis file exists only for self-build repair-loop validation.\n",
        encoding="utf-8",
    )


def test_self_build_plan_and_proposal_do_not_write(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# XV8\n", encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))
    task = manager.create_task(SelfBuildRequest(user_prompt="Self-build test. Inspect README.md and propose a patch that adds Self-Build Mode. Do not commit."))
    assert task.plan is not None
    assert task.proposal is not None
    assert task.proposal.validation.passed is True
    assert "Self-Build Mode" not in readme.read_text(encoding="utf-8")
    assert task.proposal.approval_id


def test_self_build_apply_requires_approval_and_hash_match(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# XV8\n", encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))
    task = manager.create_task(SelfBuildRequest(user_prompt="Self-build test. Inspect README.md and propose a patch that adds Self-Build Mode. Do not commit."))
    proposal = task.proposal
    assert proposal is not None
    denied = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=False))
    assert denied.applied is False
    mismatch = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash="bad", approved=True))
    assert mismatch.applied is False
    bad_approval = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id="wrong", patch_hash=proposal.patch_hash, approved=True))
    assert bad_approval.applied is False
    bad_patch = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id="wrong", approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=True))
    assert bad_patch.applied is False
    applied = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=True))
    assert applied.applied is True
    assert "Self-Build Mode" in readme.read_text(encoding="utf-8")
    assert applied.validation_passed is True


def test_self_build_apply_blocks_if_file_changed_since_proposal(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# XV8\n", encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))
    task = manager.create_task(SelfBuildRequest(user_prompt="Self-build test. Inspect README.md and propose a patch that adds Self-Build Mode. Do not commit."))
    proposal = task.proposal
    assert proposal is not None
    readme.write_text("# XV8\n\nChanged outside proposal.\n", encoding="utf-8")

    result = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=True))

    assert result.applied is False
    assert result.status == "blocked"
    assert "changed since proposal" in result.reason
    assert "Self-Build Mode" not in readme.read_text(encoding="utf-8")


def test_self_build_smoke_proposal_creates_non_empty_bounded_patch(tmp_path) -> None:
    create_self_build_smoke_workspace(tmp_path)
    manager = SelfBuildManager(str(tmp_path))

    task = manager.create_task(SelfBuildRequest(user_prompt="create a self-build proposal to add a timestamped validation note to the self-build apply proof file"))
    detail = manager.proposal_detail(task)

    assert task.proposal is not None
    assert task.proposal.validation.passed is True
    assert task.proposal.approval_id
    assert detail["task_id"] == task.task_id
    assert detail["patch_id"] == task.proposal.patch_id
    assert detail["approval_id"] == task.proposal.approval_id
    assert detail["patch_hash"] == task.proposal.patch_hash
    assert detail["changed_file_paths"] == ["runtime/self_build_smoke/approved_apply_proof.md"]
    assert detail["changes"][0]["before_hash"]
    assert detail["changes"][0]["after_hash"]
    assert detail["changes"][0]["before_hash"] != detail["changes"][0]["after_hash"]
    assert "self-build approved apply proof" in detail["changes"][0]["unified_diff"]
    assert detail["tests_to_run"] == ["architecture_guard"]
    assert detail["rollback_plan"]
    assert detail["apply_safe"] is True


def test_self_build_smoke_denied_approved_duplicate_and_readiness(tmp_path) -> None:
    create_self_build_smoke_workspace(tmp_path)
    proof = tmp_path / "runtime" / "self_build_smoke" / "approved_apply_proof.md"
    original = proof.read_text(encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))
    assert manager.trust_status()["readiness"]["message"] == "FAILED: approved self-build apply was not proven."
    task = manager.create_task(SelfBuildRequest(user_prompt="create a self-build proposal to add a timestamped validation note to the self-build apply proof file"))
    proposal = task.proposal
    assert proposal is not None

    denied = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=False))
    assert denied.applied is False
    assert proof.read_text(encoding="utf-8") == original
    assert manager.trust_status()["readiness"]["approved_apply_proven"] is False

    applied = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=True))
    assert applied.applied is True
    assert applied.changed_files == ["runtime/self_build_smoke/approved_apply_proof.md"]
    assert applied.backup_paths
    assert "self-build approved apply proof" in proof.read_text(encoding="utf-8")
    assert manager.trust_status()["readiness"]["approved_apply_proven"] is True
    assert manager.trust_status()["readiness"]["status"] == "passed"

    duplicate = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=True))
    assert duplicate.applied is False
    assert duplicate.status == "blocked"
    assert "already applied" in duplicate.reason


def test_self_build_smoke_stale_apply_is_blocked(tmp_path) -> None:
    create_self_build_smoke_workspace(tmp_path)
    proof = tmp_path / "runtime" / "self_build_smoke" / "approved_apply_proof.md"
    manager = SelfBuildManager(str(tmp_path))
    task = manager.create_task(SelfBuildRequest(user_prompt="create a self-build proposal to add a timestamped validation note to the self-build apply proof file"))
    proposal = task.proposal
    assert proposal is not None
    proof.write_text(proof.read_text(encoding="utf-8") + "\nManual stale edit.\n", encoding="utf-8")

    stale = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=True))

    assert stale.applied is False
    assert stale.status == "blocked"
    assert "changed since proposal" in stale.reason


def test_self_build_rejects_outside_destructive_and_unbounded_requests(tmp_path) -> None:
    create_self_build_smoke_workspace(tmp_path)
    manager = SelfBuildManager(str(tmp_path))

    outside = manager.create_task(SelfBuildRequest(user_prompt="create a self-build proposal to add a timestamped validation note to ../outside.md"))
    assert outside.proposal is not None
    assert outside.proposal.validation.passed is False
    assert outside.proposal.approval_id == ""
    assert manager.proposal_detail(outside)["apply_safe"] is False

    destructive = manager.create_task(SelfBuildRequest(user_prompt="create a self-build proposal to delete the self-build apply proof file"))
    assert destructive.proposal is not None
    assert destructive.proposal.validation.passed is False
    assert destructive.proposal.approval_id == ""
    assert "Destructive" in destructive.proposal.validation.reasons[-1]

    mixed_destructive = manager.create_task(SelfBuildRequest(user_prompt="create a self-build proposal to add a timestamped validation note and delete the self-build apply proof file"))
    assert mixed_destructive.proposal is not None
    assert mixed_destructive.proposal.validation.passed is False
    assert mixed_destructive.proposal.approval_id == ""
    assert not mixed_destructive.proposal.changes

    unbounded = manager.create_task(SelfBuildRequest(user_prompt="create a self-build proposal to improve the system"))
    assert unbounded.proposal is not None
    assert unbounded.proposal.validation.passed is False
    assert unbounded.plan is not None
    assert "bounded safe target path" in unbounded.plan.known_limitations[0]


def test_self_build_validation_presets_are_allowlisted(tmp_path) -> None:
    manager = SelfBuildManager(str(tmp_path))
    result = manager.validation.validate_presets(["architecture_guard", "npm_install"])
    assert result.passed is False
    assert "npm_install" in result.reasons[0]


def test_self_build_noop_change_fails_validation(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# XV8\n", encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))
    current = readme.read_text(encoding="utf-8")
    digest = manager.proposals._hash_text(current)
    result = manager.validation.validate(
        [
            PatchFileChange(
                file_path="README.md",
                before_hash=digest,
                after_hash=digest,
                proposed_content=current,
                unified_diff="",
            )
        ]
    )
    assert result.passed is False
    assert result.status == "failed"
    assert any("No code changes were generated" in reason for reason in result.reasons)


def test_self_build_supported_release_task_types_generate_bounded_changes(tmp_path) -> None:
    create_ui_workspace(tmp_path)
    (tmp_path / "README.md").write_text("# XV8\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("X8_ENV=development\n", encoding="utf-8")
    project_builder = tmp_path / "apps" / "api" / "src" / "x8" / "project_builder"
    self_build = tmp_path / "apps" / "api" / "src" / "x8" / "self_build"
    routes = tmp_path / "apps" / "api" / "src" / "x8" / "api" / "routes"
    tests = tmp_path / "apps" / "api" / "tests"
    project_builder.mkdir(parents=True, exist_ok=True)
    self_build.mkdir(parents=True, exist_ok=True)
    routes.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    (project_builder / "manager.py").write_text("class ProjectBuilderManager:\n    pass\n", encoding="utf-8")
    (routes / "project_builder.py").write_text("from fastapi import APIRouter\nrouter = APIRouter()\n", encoding="utf-8")
    (routes / "self_build.py").write_text("from fastapi import APIRouter\nrouter = APIRouter()\n", encoding="utf-8")
    (self_build / "manager.py").write_text("class SelfBuildManager:\n    pass\n", encoding="utf-8")
    (tests / "test_project_builder_contracts.py").write_text("def test_existing() -> None:\n    assert True\n", encoding="utf-8")
    (tests / "test_api_contracts.py").write_text("def test_existing_api() -> None:\n    assert True\n", encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))
    prompts = {
        "ui_feature": "Self-build proposal add a UI panel for release status",
        "api_feature": "Self-build proposal add an API endpoint manager feature",
        "test_only": "Self-build proposal add test only coverage",
        "docs_only": "Self-build proposal update README documentation",
        "config_change": "Self-build proposal update safe config",
        "repair_patch": "Self-build proposal repair patch for a small bug fix",
        "project_builder_feature": "Self-build proposal improve Project Builder generated project feature",
    }
    for expected_type, prompt in prompts.items():
        task = manager.create_task(SelfBuildRequest(user_prompt=prompt))
        detail = manager.proposal_detail(task)
        assert detail["task_type"] == expected_type
        assert detail["apply_safe"] is True
        assert detail["changed_file_paths"]
        assert detail["changes"][0]["before_hash"] != detail["changes"][0]["after_hash"]


def test_self_build_validate_task_records_report(tmp_path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# XV8\n", encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))
    task = manager.create_task(SelfBuildRequest(user_prompt="Self-build test. Inspect README.md and propose a patch. Do not commit.", test_presets=["architecture_guard"]))

    def fake_run_presets(presets):
        from x8.self_build.contracts import SelfBuildTestRun

        return [SelfBuildTestRun(preset=presets[0], ran=True, passed=True, command=["docker", "compose"], exit_code=0, status="passed")]

    monkeypatch.setattr(manager.validation, "run_presets", fake_run_presets)
    report = manager.validate_task(task.task_id)

    assert report.validation_passed is True
    assert report.validation_runs[0].preset == "architecture_guard"
    assert task.validation_reports[0].report_id == report.report_id


def test_self_build_api_creates_task_without_applying(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# XV8\n", encoding="utf-8")
    api = client(Settings(workspace_root=str(tmp_path), knowledge_root="/app/knowledge", ollama_base_url="http://127.0.0.1:9", default_chat_model="", fallback_chat_model="", x7_import_root="/missing/x7", x6_import_root="/missing/x6"))
    response = api.post("/api/self-build/tasks", json={"user_prompt": "Self-build test. Inspect README.md and propose a patch. Do not commit."})
    payload = response.json()
    assert payload["status"] == "planned"
    assert payload["data"]["proposal"]["approval_id"]
    assert "Self-Build Mode" not in (tmp_path / "README.md").read_text(encoding="utf-8")


def test_self_build_prompt_route_read_only_inspects_latest_without_creating(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# XV8\n", encoding="utf-8")
    api = client(Settings(workspace_root=str(tmp_path), knowledge_root="/app/knowledge", ollama_base_url="http://127.0.0.1:9", default_chat_model="", fallback_chat_model="", x7_import_root="/missing/x7", x6_import_root="/missing/x6"))

    created = api.post("/api/self-build/prompt", json={"prompt": "Self-build test. Inspect README.md and add a Self-Build Mode section. Do not commit."}).json()
    assert created["status"] == "planned"
    original_task_id = created["data"]["proposal_detail"]["task_id"]
    original_patch_hash = created["data"]["proposal_detail"]["patch_hash"]
    assert created["data"]["proposal_detail"]["patch_id"]
    assert created["data"]["proposal_detail"]["approval_id"]
    assert created["data"]["proposal_detail"]["message"] == "No files changed. Approval required before apply."

    inspected = api.post("/api/self-build/prompt", json={"prompt": "Show the full self-build patch proposal details before approval"}).json()
    assert inspected["status"] == "proposed"
    assert inspected["data"]["intent"] == "inspect_proposal"
    assert inspected["data"]["proposal_detail"]["task_id"] == original_task_id
    assert inspected["data"]["proposal_detail"]["patch_hash"] == original_patch_hash
    assert inspected["data"]["proposal_detail"]["changed_file_paths"] == ["README.md"]
    assert inspected["data"]["proposal_detail"]["changes"][0]["before_hash"]
    assert inspected["data"]["proposal_detail"]["changes"][0]["after_hash"]
    assert inspected["data"]["proposal_detail"]["changes"][0]["unified_diff"]
    assert inspected["data"]["proposal_detail"]["validation_status"] == "passed"
    assert inspected["data"]["proposal_detail"]["apply_safe"] is True

    latest = api.get("/api/self-build/tasks/latest/proposal").json()
    assert latest["data"]["task_id"] == original_task_id
    assert latest["data"]["patch_hash"] == original_patch_hash


def test_self_build_build_prompt_mentions_trust_status_but_creates_one_proposal(tmp_path) -> None:
    create_ui_workspace(tmp_path)
    api = client(Settings(workspace_root=str(tmp_path), knowledge_root="/app/knowledge", ollama_base_url="http://127.0.0.1:9", default_chat_model="", fallback_chat_model="", x7_import_root="/missing/x7", x6_import_root="/missing/x6"))
    build_prompt = "Self-build task: run a controlled proposal-only improvement. Add a small UI label or dashboard card that displays the current self-build trust status using the existing trust-status endpoint. Rules: Proposal only first. Do not write files until I approve the exact patch hash. Show exact files to change. Include unified diff. Include validation commands. Include rollback plan."

    created = api.post("/api/self-build/prompt", json={"prompt": build_prompt}).json()

    assert created["status"] == "planned"
    assert created["data"]["intent"] == "create_proposal"
    original = created["data"]["proposal_detail"]
    assert original["task_id"]
    assert original["patch_id"]
    assert original["approval_id"]
    assert original["patch_hash"]
    assert original["message"] == "No files changed. Approval required before apply."
    assert "README.md" not in original["changed_file_paths"]
    assert any(path.startswith("apps/web/src/") for path in original["changed_file_paths"])
    assert original["task_type"] == "ui_feature"
    assert "architecture_guard" in original["tests_to_run"]
    assert "web_tests" in original["tests_to_run"]
    assert "web_build" in original["tests_to_run"]
    assert all(change["before_hash"] and change["after_hash"] and change["before_hash"] != change["after_hash"] and change["unified_diff"] for change in original["changes"])
    assert all(change["proposed_content_preview"] for change in original["changes"])
    assert "loadSelfBuildTrustStatus" in "\n".join(change["unified_diff"] for change in original["changes"])
    assert "Self-build trust gate" in "\n".join(change["unified_diff"] for change in original["changes"])
    assert "Validation preset count" in "\n".join(change["unified_diff"] for change in original["changes"])
    assert "#22d3ee" in "\n".join(change["unified_diff"] for change in original["changes"])
    assert "Self-build trust gate" not in (tmp_path / "apps" / "web" / "src" / "app" / "App.tsx").read_text(encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))
    task = manager.create_task(SelfBuildRequest(user_prompt=build_prompt))
    assert task.proposal is not None
    original_hash = task.proposal.patch_hash
    task.proposal.changes[0].proposed_content += "\n// hash check\n"
    assert manager.proposals.hash_changes(task.proposal.changes) != original_hash

    inspected = api.post("/api/self-build/prompt", json={"prompt": "Show the full latest self-build patch proposal details before approval. Do not create a new proposal. Do not apply. Do not write anything."}).json()
    assert inspected["status"] == "proposed"
    assert inspected["data"]["intent"] == "inspect_proposal"
    assert inspected["data"]["proposal_detail"]["task_id"] == original["task_id"]
    assert inspected["data"]["proposal_detail"]["patch_id"] == original["patch_id"]
    assert inspected["data"]["proposal_detail"]["patch_hash"] == original["patch_hash"]

    latest = api.get("/api/self-build/tasks/latest/proposal").json()
    assert latest["data"]["task_id"] == original["task_id"]
    assert latest["data"]["patch_id"] == original["patch_id"]
    assert latest["data"]["patch_hash"] == original["patch_hash"]
    assert all(change["unified_diff"] and change["before_hash"] != change["after_hash"] for change in latest["data"]["changes"])


def test_self_build_noop_proposal_is_blocked_without_approval(tmp_path) -> None:
    create_ui_workspace(tmp_path)
    app = tmp_path / "apps" / "web" / "src" / "app" / "App.tsx"
    client_file = tmp_path / "apps" / "web" / "src" / "services" / "apiClient.ts"
    app.write_text(SelfBuildManager(str(tmp_path)).proposals._add_trust_status_card(app.read_text(encoding="utf-8")), encoding="utf-8")
    client_file.write_text(SelfBuildManager(str(tmp_path)).proposals._add_trust_status_client(client_file.read_text(encoding="utf-8")), encoding="utf-8")
    manager = SelfBuildManager(str(tmp_path))

    task = manager.create_task(SelfBuildRequest(user_prompt="Self-build task: Add a small UI label or dashboard card that displays the current self-build trust status using the existing trust-status endpoint. Proposal only first."))
    detail = manager.proposal_detail(task)

    assert task.proposal is not None
    assert task.proposal.status == "blocked"
    assert task.proposal.approval_id == ""
    assert task.proposal.validation.status == "failed"
    assert any("No code changes were generated" in reason for reason in task.proposal.validation.reasons)
    assert detail["apply_safe"] is False
    assert detail["message"] == "No code changes were generated."


def test_self_build_ui_feature_without_visible_render_is_blocked(tmp_path) -> None:
    create_ui_workspace(tmp_path)
    manager = SelfBuildManager(str(tmp_path))
    manager.proposals._add_trust_status_card = lambda before: before  # type: ignore[method-assign]

    task = manager.create_task(SelfBuildRequest(user_prompt="Self-build task: Add a small UI label or dashboard card that displays the current self-build trust status using the existing trust-status endpoint. Proposal only first."))
    detail = manager.proposal_detail(task)

    assert task.proposal is not None
    assert task.proposal.status == "blocked"
    assert task.proposal.approval_id == ""
    assert task.proposal.validation.status == "failed"
    assert "UI feature proposal did not generate visible Self-build trust gate JSX." in task.proposal.validation.reasons
    assert detail["apply_safe"] is False


def test_self_build_exact_approval_applies_ui_proposed_content(tmp_path) -> None:
    create_ui_workspace(tmp_path)
    manager = SelfBuildManager(str(tmp_path))
    task = manager.create_task(SelfBuildRequest(user_prompt="Self-build task: Add a small UI label or dashboard card that displays the current self-build trust status using the existing trust-status endpoint. Proposal only first."))
    proposal = task.proposal
    assert proposal is not None
    app_change = next(change for change in proposal.changes if change.file_path == "apps/web/src/app/App.tsx")

    result = manager.apply_patch(task.task_id, PatchApplyRequest(patch_id=proposal.patch_id, approval_id=proposal.approval_id, patch_hash=proposal.patch_hash, approved=True))

    assert result.applied is True
    assert (tmp_path / "apps" / "web" / "src" / "app" / "App.tsx").read_text(encoding="utf-8") == app_change.proposed_content
    report = manager.validate_task(task.task_id)
    assert report.patch_hash == proposal.patch_hash
    assert report.applied is True
    assert report.reverted is False
    assert report.failure_reason in {"", "One or more self-build validation presets failed or did not run."}


def test_self_build_read_only_status_prompts_do_not_create_proposals(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# XV8\n", encoding="utf-8")
    api = client(Settings(workspace_root=str(tmp_path), knowledge_root="/app/knowledge", ollama_base_url="http://127.0.0.1:9", default_chat_model="", fallback_chat_model="", x7_import_root="/missing/x7", x6_import_root="/missing/x6"))

    trust = api.post("/api/self-build/prompt", json={"prompt": "Show self-build trust status."}).json()
    assert trust["status"] == "ready"
    assert trust["data"]["intent"] == "trust_status"

    validation = api.post("/api/self-build/prompt", json={"prompt": "Show latest self-build validation report."}).json()
    assert validation["status"] == "missing"
    assert validation["message"] == "No active self-build proposal found."

    latest = api.get("/api/self-build/tasks/latest/proposal").json()
    assert latest["status"] == "missing"
    assert latest["message"] == "No active self-build proposal found."


def test_self_build_api_reports_trust_status(tmp_path) -> None:
    api = client(Settings(workspace_root=str(tmp_path), knowledge_root="/app/knowledge", ollama_base_url="http://127.0.0.1:9", default_chat_model="", fallback_chat_model="", x7_import_root="/missing/x7", x6_import_root="/missing/x6"))
    payload = api.get("/api/self-build/trust-status").json()
    assert payload["status"] == "ready"
    assert payload["data"]["approval_hash_required"] is True
    assert payload["data"]["writes_without_approval"] is False


def test_operator_capabilities_route_reports_scaffold() -> None:
    payload = client().get("/api/operator/capabilities").json()
    assert payload["status"] == "ready"
    assert any(item["capability_id"] == "operator.workspace_read" for item in payload["data"])


def test_operator_mutating_task_produces_approval_without_execution() -> None:
    payload = client().post("/api/operator/tasks", json={"prompt": "edit README.md", "action_type": "write_file", "target_identifier": "README.md"}).json()
    assert payload["data"]["approvals"]
    assert payload["data"]["results"] == []
