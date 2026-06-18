from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.settings import Settings
from x8.managers.x7_config_import_manager import LegacyConfigImportManager, X7ConfigImportManager
from x8.managers.legacy_brain_import_manager import LegacyBrainImportManager
from x8.managers.avatar_manager import AvatarAssetImportManager
from x8.managers.speech_manager import SpeechManager, SpeechPreferenceManager, TextToSpeechAdapter
from x8.kernel.brain_context import BrainContextAssembler
from x8.kernel.capability_registry import CapabilityRegistration, default_registry
from x8.kernel.contracts import JobRequest, JobStatus, KernelRequest
from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.kernel import UNAVAILABLE, XV8Kernel
from x8.kernel.model_router import ModelProfileManager, ModelRouter
from x8.kernel.prompt_builder import KernelPromptBuilder
from x8.kernel.response_planner import ResponsePlanner
from x8.managers.model_manager import OllamaAdapter
from x8.managers.memory_manager import MemoryApprovalDecision, MemoryManager, MemoryProposal
from x8.managers.model_manager import ModelReadinessManager
from x8.self_build.contracts import PatchApplyRequest, SelfBuildRequest
from x8.self_build.manager import SelfBuildManager
from x8.self_build.prompt_ingestor import BuildPromptIngestor
from x8.self_build.repo_context import RepoContextReader


def client(settings: Settings | None = None) -> TestClient:
    if settings is None:
        settings = Settings(
            knowledge_root="/app/knowledge",
            x7_import_root="/missing/x7",
            x6_import_root="/missing/x6",
        )
        settings.ollama_base_url = "http://127.0.0.1:9"
        settings.default_chat_model = ""
        settings.fallback_chat_model = ""
        settings.code_model = ""
        settings.reasoning_model = ""
    return TestClient(create_app(settings))


def test_health() -> None:
    response = client().get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_capability_truth_model() -> None:
    response = client().get("/api/capabilities")
    names = {item["name"]: item["status"] for item in response.json()["data"]}
    assert names["artifact_preview"] == "implemented"
    assert names["email_send"] == "disabled"
    assert names["remote_access"] == "disabled"


def test_chat_returns_receipt() -> None:
    response = client().post("/api/chat", json={"message": "Plan a safe build"})
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["assistant_message"]["role"] == "assistant"
    assert payload["data"]["receipt"]["action_type"] == "prompt_round_trip"
    assert payload["receipts"][0]["action"] == "prompt_round_trip"
    assert "kernel_lane" in payload["receipts"][0]["metadata"]


def test_chat_does_not_fake_model_response_when_unavailable() -> None:
    response = client().post("/api/chat", json={"message": "hello XV8"})
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["data"]["assistant_message"]["content"] == "The assistant model is unavailable right now.\nNo model response was generated.\nCheck Settings > Model + Runtime."


def test_kernel_unavailable_model_returns_honest_response(tmp_path) -> None:
    kernel = XV8Kernel(
        KernelContextAssembler(BrainContextAssembler(str(tmp_path), {"context_max_messages": 20, "context_max_attachment_chars": 20, "context_max_memory_items": 20, "context_max_knowledge_items": 20}), KernelPromptBuilder()),
        ModelRouter(OllamaAdapter("http://127.0.0.1:9"), ModelProfileManager("", "")),
    )
    response = kernel.handle(KernelRequest(session_id="sess_test", user_message="hello"))
    assert response.assistant_message == UNAVAILABLE
    assert response.receipt.kernel_lane == "normal_chat"
    assert response.receipt.context_sources_used


def test_kernel_context_sources_stay_separated_and_truncate_attachments(tmp_path) -> None:
    (tmp_path / "team.md").write_text("knowledge item", encoding="utf-8")
    assembler = BrainContextAssembler(str(tmp_path), {"context_max_messages": 1, "context_max_attachment_chars": 5, "context_max_memory_items": 20, "context_max_knowledge_items": 20})
    bundle = assembler.assemble(
        [{"role": "user", "content": "first"}, {"role": "assistant", "content": "second"}],
        [{"filename": "notes.txt", "extracted_text": "abcdefghi"}],
    )
    assert bundle.memory == []
    assert bundle.research == []
    assert bundle.knowledge[0].startswith("team.md")
    assert bundle.session_context == ["assistant: second"]
    assert bundle.attachments == ["notes.txt: abcde"]
    assert any("truncated" in item for item in bundle.limitations)


def test_kernel_context_includes_active_memory_when_ready(tmp_path) -> None:
    memory = MemoryManager(str(tmp_path / "memory.json"))
    record, _ = memory.propose(MemoryProposal(memory_type="project_fact", source="user_explicit", text="XV8 uses qwen3:8b for normal chat.", confidence=0.99))
    assert record is not None
    assembler = BrainContextAssembler(str(tmp_path), {"context_max_messages": 2, "context_max_attachment_chars": 20, "context_max_memory_items": 5, "context_max_knowledge_items": 20}, memory)
    bundle = assembler.assemble([{"role": "user", "content": "What model does XV8 use for normal chat?"}], [])
    assert any("qwen3:8b" in item for item in bundle.memory)


def test_kernel_context_reports_memory_unavailable_without_manager(tmp_path) -> None:
    assembler = BrainContextAssembler(str(tmp_path), {"context_max_messages": 2, "context_max_attachment_chars": 20, "context_max_memory_items": 5, "context_max_knowledge_items": 20})
    bundle = assembler.assemble([{"role": "user", "content": "remembered fact?"}], [])
    assert "memory_recall: unavailable; reason: embedding model or vector store not ready" in bundle.limitations


def test_kernel_lane_classification() -> None:
    planner = ResponsePlanner()
    assert planner.classify("hello XV8") == "normal_chat"
    assert planner.classify("generate an image") == "image_generation"
    assert planner.classify("search SearXNG for this") == "web_search"
    assert planner.classify("open README.md") == "repo_inspection"
    assert planner.classify("hello", has_attachments=True) == "attachment_question"


def test_model_router_selects_fallback_when_default_missing() -> None:
    class Adapter:
        def models(self):
            return True, ["fallback-model"], ""

        def generate(self, model: str, prompt: str):
            return True, "ok", ""

    _, selection = ModelRouter(Adapter(), ModelProfileManager("missing-model", "fallback-model")).select("normal_chat")  # type: ignore[arg-type]
    assert selection.selected_model == "fallback-model"
    assert selection.fallback_used is True


def test_model_readiness_reports_host_ollama_role_map() -> None:
    class Adapter:
        base_url = "http://host.docker.internal:11434"

        def models(self):
            return True, ["qwen3:8b", "qwen3:14b", "qwen3:1.7b", "qwen3-coder:30b", "nomic-embed-text:latest"], ""

        def generate(self, model: str, prompt: str):
            return True, "XV8_READY", ""

    status = ModelReadinessManager(
        Adapter(),
        "qwen3:8b",
        "qwen3:1.7b",
        ollama_mode="host_ollama_bridge",
        reasoning_model="qwen3:14b",
        code_model="qwen3:8b",
        embedding_model="nomic-embed-text:latest",
    ).status()  # type: ignore[arg-type]
    assert status.ollama_mode == "host_ollama_bridge"
    assert status.ollama_base_url == "http://host.docker.internal:11434"
    assert status.selected_model == "qwen3:8b"
    assert status.reasoning_model == "qwen3:14b"
    assert status.code_model == "qwen3:8b"
    assert status.embedding_model == "nomic-embed-text:latest"
    assert status.blocked_models == ["qwen3-coder:30b"]
    assert status.installed_but_blocked == ["qwen3-coder:30b"]
    assert status.embedding_ready is True
    assert status.model_ready is True


def test_model_router_maps_qwen_roles() -> None:
    class Adapter:
        def models(self):
            return True, ["qwen3:8b", "qwen3:14b", "qwen3:1.7b", "qwen3-coder:30b", "nomic-embed-text:latest"], ""

        def generate(self, model: str, prompt: str):
            return True, "ok", ""

    router = ModelRouter(Adapter(), ModelProfileManager("qwen3:8b", "qwen3:1.7b", "qwen3:8b", fast="qwen3:1.7b", embedding="nomic-embed-text:latest", reasoning="qwen3:14b"))  # type: ignore[arg-type]
    assert router.select("normal_chat")[1].selected_model == "qwen3:8b"
    assert router.select("reasoning")[1].selected_model == "qwen3:14b"
    assert router.select("code_help")[1].selected_model == "qwen3:8b"
    assert router.select("fast")[1].selected_model == "qwen3:1.7b"


def test_model_router_records_timeout_fallback_to_light_model() -> None:
    from x8.managers.model_manager import GenerateResult

    class Adapter:
        base_url = "http://host.docker.internal:11434"

        def __init__(self) -> None:
            self.last_generation_result = GenerateResult(ok=False)

        def models(self):
            return True, ["qwen3:8b", "qwen3:1.7b"], ""

        def generate(self, model: str, prompt: str):
            self.last_generation_result = GenerateResult(
                ok=True,
                content="fallback response",
                model="qwen3:1.7b",
                timed_out=True,
                timeout_seconds=120,
                fallback_used=True,
                failure_reason="Primary model qwen3:8b timed out after 120s. Fallback model qwen3:1.7b responded.",
            )
            return True, "fallback response", self.last_generation_result.failure_reason

    router = ModelRouter(Adapter(), ModelProfileManager("qwen3:8b", "qwen3:1.7b"))  # type: ignore[arg-type]
    _, selection = router.select("normal_chat")
    ok, content, _ = router.generate(selection, "hello")
    assert ok is True
    assert content == "fallback response"
    assert selection.selected_model == "qwen3:1.7b"
    assert selection.fallback_used is True
    assert selection.timed_out is True


def test_blocked_qwen_coder_is_never_selected() -> None:
    class Adapter:
        def models(self):
            return True, ["qwen3:8b", "qwen3:14b", "qwen3-coder:30b"], ""

        def generate(self, model: str, prompt: str):
            return True, "ok", ""

    status, selection = ModelRouter(Adapter(), ModelProfileManager("qwen3:8b", "qwen3:1.7b", "qwen3-coder:30b")).select("code_help")  # type: ignore[arg-type]
    assert selection.selected_model == "qwen3:8b"
    assert selection.selected_model != "qwen3-coder:30b"
    assert status.blocked_model_configured == ["qwen3-coder:30b"]
    assert status.installed_but_blocked == ["qwen3-coder:30b"]


def test_blocked_model_configured_in_readiness_is_ignored() -> None:
    class Adapter:
        base_url = "http://host.docker.internal:11434"

        def models(self):
            return True, ["qwen3:8b", "qwen3:14b", "qwen3-coder:30b", "nomic-embed-text:latest"], ""

        def generate(self, model: str, prompt: str):
            return True, "XV8_READY", ""

    status = ModelReadinessManager(Adapter(), "qwen3:8b", "qwen3:1.7b", code_model="qwen3-coder:30b", embedding_model="nomic-embed-text:latest").status()  # type: ignore[arg-type]
    assert status.code_model == "qwen3:8b"
    assert status.selected_model == "qwen3:8b"
    assert status.blocked_model_configured == ["qwen3-coder:30b"]


def test_embedding_model_missing_blocks_memory_not_basic_chat() -> None:
    class Adapter:
        base_url = "http://host.docker.internal:11434"

        def models(self):
            return True, ["qwen3:8b"], ""

        def generate(self, model: str, prompt: str):
            return True, "XV8_READY", ""

    status = ModelReadinessManager(Adapter(), "qwen3:8b", "qwen3:1.7b", embedding_model="nomic-embed-text:latest").status()  # type: ignore[arg-type]
    assert status.model_ready is True
    assert status.embedding_ready is False
    assert status.memory_ready is False
    assert "nomic-embed-text:latest" in status.missing_models


def test_extension_registry_and_jobs_are_versioned() -> None:
    registry = default_registry()
    registry.register(CapabilityRegistration("mock.disabled", "Mock", "test", status="not_configured", enabled=False))
    assert registry.health("mock.disabled") == "disabled"
    job = JobRequest(capability_id="image.comfyui")
    status = JobStatus(job_id=job.job_id, state="queued", summary="Queued for worker.")
    assert job.tool_contract_version == "tool.v1"
    assert status.state == "queued"


def test_attachment_upload_extracts_small_text(tmp_path) -> None:
    settings = Settings(knowledge_root="/app/knowledge", attachment_storage_path=str(tmp_path))
    response = client(settings).post("/api/attachments", files={"file": ("notes.txt", b"hello attachment", "text/plain")})
    payload = response.json()
    assert payload["status"] == "uploaded"
    assert payload["data"]["content_extractable"] is True
    assert payload["data"]["extracted_text"] == "hello attachment"
    assert payload["receipts"][0]["action"] == "attachment_extracted"


def test_attachment_upload_blocks_oversized_file(tmp_path) -> None:
    settings = Settings(knowledge_root="/app/knowledge", attachment_storage_path=str(tmp_path), attachment_max_mb=0)
    response = client(settings).post("/api/attachments", files={"file": ("large.txt", b"x", "text/plain")})
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["receipts"][0]["action"] == "attachment_blocked"


def test_session_persists_messages_and_attachments(tmp_path) -> None:
    settings = Settings(knowledge_root="/app/knowledge", attachment_storage_path=str(tmp_path))
    api = client(settings)
    upload = api.post("/api/attachments", files={"file": ("context.md", b"# Context", "text/markdown")}).json()["data"]
    chat = api.post(
        "/api/chat",
        json={
            "message": "Use this context",
            "attachments": [
                {
                    "attachment_id": upload["attachment_id"],
                    "filename": upload["filename"],
                    "mime_type": upload["mime_type"],
                    "size_bytes": upload["size_bytes"],
                }
            ],
        },
    ).json()
    session = api.get(f"/api/sessions/{chat['data']['session_id']}").json()["data"]
    assert len(session["messages"]) >= 2
    assert session["messages"][0]["attachments"][0]["filename"] == "context.md"
    assert session["receipts"][0]["action_type"] == "prompt_round_trip"


def test_models_status_and_receipts_endpoints_exist() -> None:
    api = client()
    model_status = api.get("/api/models/status")
    assert model_status.status_code == 200
    assert model_status.json()["data"]["ollama_mode"] == "host_ollama_bridge"
    assert api.get("/api/memory/status").status_code == 200
    chat = api.post("/api/chat", json={"message": "receipt check"}).json()
    receipts = api.get("/api/receipts").json()["data"]
    assert any(item["receipt_id"] == chat["data"]["receipt"]["receipt_id"] for item in receipts)


def test_artifact_preview_does_not_mutate_repo() -> None:
    response = client().post("/api/artifacts/preview", json={"title": "Demo", "prompt": "Make a dashboard"})
    artifact = response.json()["data"]
    assert artifact["mutated_repo"] is False
    assert "index.html" in artifact["files"]


def test_repo_write_denied_without_approval() -> None:
    response = client().post("/api/repo/write-probe")
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["data"]["allowed"] is False


def test_github_reports_not_configured_without_token() -> None:
    response = client().get("/api/github/status")
    data = response.json()["data"]
    assert data["status"] == "not_configured"
    assert data["capability"] == "unavailable"


def test_workspace_file_tree_and_read() -> None:
    response = client().get("/api/workspace/files")
    assert response.status_code == 200
    read = client().post("/api/workspace/read", json={"path": "README.md"})
    assert read.status_code == 200
    assert "XV8" in read.json()["data"]["content"]
    assert read.json()["receipts"][0]["action"] == "workspace.read_file"


def test_patch_proposal_does_not_mutate() -> None:
    current = client().post("/api/workspace/read", json={"path": "README.md"}).json()["data"]["content"]
    response = client().post("/api/repo/propose-update", json={"path": "README.md", "proposed_content": current + "\n"})
    proposal = response.json()["data"]
    assert proposal["mutated"] is False
    assert proposal["diff"]


def test_patch_apply_creates_click_approval_without_mutation() -> None:
    current = client().post("/api/workspace/read", json={"path": "README.md"}).json()["data"]["content"]
    response = client().post("/api/repo/apply-update", json={"path": "README.md", "proposed_content": current + "\n", "approved": False})
    proposal = response.json()["data"]
    assert proposal["mutated"] is False
    assert proposal["approval"]["status"] == "pending_click"
    assert proposal["approval"]["typed_confirmation"] is None


def test_destructive_action_creates_destructive_modal_request() -> None:
    response = client().post(
        "/api/approvals/request",
        json={"action": "git.push", "risk": "high_risk", "target": "origin/main", "summary": "Push branch", "destructive": True},
    )
    approval = response.json()["data"]
    assert approval["risk"] == "destructive"
    assert approval["status"] == "pending_click"


def test_docker_preset_does_not_claim_success_without_execution() -> None:
    response = client().post("/api/docker/run-preset", json={"preset_name": "api_tests"})
    payload = response.json()
    assert payload["status"] == "pending_click"
    assert payload["data"]["exit_code"] is None


def test_read_only_docker_preset_attempts_real_execution_or_honest_unavailable() -> None:
    response = client().post("/api/docker/run-preset", json={"preset_name": "service_status"})
    payload = response.json()
    assert payload["status"] in {"passed", "failed", "not_run_environment_unavailable"}


def test_searxng_reports_unavailable_when_service_down() -> None:
    response = client().get("/api/search/status")
    assert response.status_code == 200
    assert response.json()["data"]["status"] in {"unavailable", "available"}


def test_comfyui_missing_model_does_not_fake_generation() -> None:
    response = client().post("/api/images/generate", json={"prompt": "test", "approved": True})
    payload = response.json()
    assert payload["data"]["image_generated"] is False
    assert payload["status"] in {"model_missing", "pending_click", "queued"}


def test_x7_config_import_redacts_secrets(tmp_path) -> None:
    (tmp_path / ".env").write_text("BRAVE_SEARCH_API_KEY=abcdefxyz\nCOMFYUI_BASE_URL=http://localhost:8188\n", encoding="utf-8")
    manager = X7ConfigImportManager(str(tmp_path), "/workspace/config/migration/x7_to_xv8_env_map.yaml")
    report = manager.scan()
    names = {item.name: item for item in report.values}
    assert names["BRAVE_SEARCH_API_KEY"].redacted_preview == "abc...xyz"
    assert names["COMFYUI_BASE_URL"].redacted_preview == "http://localhost:8188"


def test_legacy_import_scans_x6_and_x7_independently(tmp_path) -> None:
    x7 = tmp_path / "x7"
    x6 = tmp_path / "x6"
    x7.mkdir()
    x6.mkdir()
    (x7 / ".env").write_text("GITHUB_TOKEN=ghp_abcdefxyz\n", encoding="utf-8")
    (x6 / ".env").write_text("COMFYUI_BASE_URL=http://localhost:8188\nSEARXNG_BASE_URL=http://localhost:8080\n", encoding="utf-8")
    manager = LegacyConfigImportManager(str(x7), str(x6), "/workspace/config/migration/x6_x7_to_xv8_env_map.yaml")
    report = manager.scan()
    assert report.x7_files_found == 1
    assert report.x6_files_found == 1
    assert "github" in report.x7_import_status.providers_found
    assert "ComfyUI" in report.x6_import_status.providers_found
    assert "SearXNG" in report.x6_import_status.providers_found


def test_legacy_brain_import_writes_redacted_reports(tmp_path) -> None:
    x7 = tmp_path / "x7"
    x6 = tmp_path / "x6"
    reports = tmp_path / "reports"
    (x7 / "data" / "brain").mkdir(parents=True)
    (x6 / "memory").mkdir(parents=True)
    (x7 / "data" / "brain" / "knowledge.md").write_text("Useful knowledge\n", encoding="utf-8")
    (x6 / "memory" / "secret-context.md").write_text("API_KEY=abcdefxyz\n", encoding="utf-8")
    report = LegacyBrainImportManager(str(x7), str(x6), str(reports)).scan()
    assert report["sources"]["x7"]["files_found"] == 1
    assert (reports / "legacy-brain-import-summary.md").exists()
    redacted = (reports / "legacy-brain-import-redacted.json").read_text(encoding="utf-8")
    assert "abcdefxyz" not in redacted
    assert "[redacted secret-like file]" in redacted
    memory_report = LegacyBrainImportManager(str(x7), str(x6), str(reports)).scan_memory_candidates()
    assert memory_report["memory_candidates"][0]["status"] == "pending"
    assert (reports / "legacy-memory-import-summary.md").exists()


def test_memory_proposal_approval_and_recall(tmp_path) -> None:
    manager = MemoryManager(str(tmp_path / "memory.json"))
    record, receipt = manager.propose(MemoryProposal(memory_type="project_fact", source="user_correction", text="XV8 project root is X:/X 8", confidence=0.8))
    assert record is not None
    assert record.status == "pending"
    assert receipt.status == "pending"
    approved, approval_receipt = manager.approve(MemoryApprovalDecision(memory_record_id=record.memory_record_id, decision="approve"))
    assert approved is not None
    assert approved.status == "active"
    results, recall_receipt = manager.recall("Where is the XV8 project root?")
    assert recall_receipt.action_type == "memory_recalled"
    assert results[0].record.text == "XV8 project root is X:/X 8"


def test_memory_blocks_secret_like_content(tmp_path) -> None:
    manager = MemoryManager(str(tmp_path / "memory.json"))
    record, receipt = manager.propose(MemoryProposal(memory_type="tool_configuration", source="user_explicit", text="API_KEY=abcdefxyz", confidence=0.99))
    assert record is None
    assert receipt.status == "blocked"
    assert "Secret-like content is blocked from memory." in receipt.limitations


def test_memory_and_verified_status_remain_separate(tmp_path) -> None:
    manager = MemoryManager(str(tmp_path / "memory.json"))
    record, _ = manager.propose(MemoryProposal(memory_type="verified_status_pointer", source="verified_status", text="Receipt rcpt_123 proves model status was checked.", confidence=0.7))
    assert record is not None
    assert record.status == "pending"
    assert manager.separation().verified_status != manager.separation().memory


def test_setup_wizard_reports_x6_and_x7_status() -> None:
    response = client().get("/api/config-import/legacy/status")
    data = response.json()["data"]
    assert data["x7_mount_path"] == "/imports/x7"
    assert data["x6_mount_path"] == "/imports/x6"
    assert "x7_import_status" in data
    assert "x6_import_status" in data


def test_local_bridge_status_endpoint_exists() -> None:
    response = client().get("/api/local-bridge/status")
    assert response.status_code == 200
    assert "bridge_reachable" in response.json()["data"]


def test_avatar_status_reports_fallback_or_ready() -> None:
    response = client().get("/api/avatar/manifest")
    payload = response.json()
    assert payload["status"] in {"ready", "degraded_fallback", "missing_assets"}
    assert payload["data"]["fallback_available"] is True


def test_avatar_status_reports_video_manifest_assets() -> None:
    response = client().get("/api/avatar/status")
    payload = response.json()
    assert payload["status"] in {"ready", "degraded_fallback", "missing_assets"}
    assert payload["data"]["manifest_found"] is True
    assert payload["data"]["video_asset_count"] == 3
    assert set(payload["data"]["states_available"]) >= {"idle", "listening", "speaking", "thinking"}
    assert payload["data"]["fallback_available"] is True


def test_avatar_import_detects_supported_assets(tmp_path) -> None:
    asset_dir = tmp_path / "public" / "avatar"
    asset_dir.mkdir(parents=True)
    (asset_dir / "xv7-avatar.svg").write_text("<svg></svg>", encoding="utf-8")
    out = tmp_path / "out"
    manifest, receipt = AvatarAssetImportManager(str(tmp_path), str(out)).import_assets()
    assert receipt.assets_imported == 1
    assert manifest.assets[0].asset_type == "svg"


def test_speech_defaults_to_us_google_female_preference() -> None:
    prefs = SpeechPreferenceManager(True, "google", "en-US", "female", "Google US English Female").preference
    status = SpeechManager(prefs, TextToSpeechAdapter("", "")).status()
    assert status.provider == "browser_speech_synthesis"
    assert status.voice == "Google US English Female"
    assert status.locale == "en-US"
    assert status.gender_preference == "female"


def test_speech_endpoint_has_browser_fallback() -> None:
    response = client().get("/api/speech/status")
    payload = response.json()
    assert payload["status"] in {"browser_fallback", "configured", "unavailable"}


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


def test_self_build_validation_presets_are_allowlisted(tmp_path) -> None:
    manager = SelfBuildManager(str(tmp_path))
    result = manager.validation.validate_presets(["architecture_guard", "npm_install"])
    assert result.passed is False
    assert "npm_install" in result.reasons[0]


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
    (tmp_path / "README.md").write_text("# XV8\n", encoding="utf-8")
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
    assert "Self-Build Mode" not in (tmp_path / "README.md").read_text(encoding="utf-8")

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
