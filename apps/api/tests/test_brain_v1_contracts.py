from uuid import uuid4

from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.brain.embedding_client import EmbeddingResult
from x8.brain.memory_manager import BrainMemoryManager
from x8.brain.memory_store import BrainMemoryStore
from x8.kernel.brain_context import BrainContextAssembler
from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.contracts import KernelRequest
from x8.kernel.kernel import XV8Kernel
from x8.kernel.model_router import ModelProfileManager, ModelRouter
from x8.kernel.prompt_builder import KernelPromptBuilder
from x8.settings import Settings


MISS = "I don’t have a saved memory for that yet."


def make_settings() -> Settings:
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
    return settings


def client(settings: Settings | None = None) -> TestClient:
    return TestClient(create_app(settings or make_settings()))


def store(settings: Settings | None = None) -> BrainMemoryStore:
    return BrainMemoryStore((settings or make_settings()).database_url)


def unique_phrase() -> str:
    return f"direct senior-engineer answers {uuid4().hex[:8]}"


class FakeEmbeddingClient:
    model = "nomic-embed-text:latest"

    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.calls: list[str] = []

    def embed(self, text: str) -> EmbeddingResult:
        self.calls.append(text)
        if not self.available:
            return EmbeddingResult(False, [], self.model, "mock embedding unavailable")
        lower = text.lower()
        if any(word in lower for word in ("respond", "answer", "senior-engineer", "direct")):
            vector = [1.0, 0.0, 0.0]
        elif any(word in lower for word in ("routing", "github", "self-build", "steal")):
            vector = [0.0, 1.0, 0.0]
        elif any(word in lower for word in ("proof", "apply", "runtime/self_build_smoke")):
            vector = [0.0, 0.0, 1.0]
        else:
            vector = [0.2, 0.2, 0.2]
        return EmbeddingResult(True, vector, self.model)


def semantic_manager(settings: Settings | None = None, available: bool = True) -> BrainMemoryManager:
    return BrainMemoryManager(
        (settings or make_settings()).database_url,
        embedding_client=FakeEmbeddingClient(available),
        embedding_model="nomic-embed-text:latest",
        retrieval_min_score=0.5,
    )


def test_manual_remember_saves_low_risk_preference() -> None:
    api = client()
    phrase = unique_phrase()
    payload = api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"}).json()
    assert payload["status"] == "passed"
    assert payload["data"]["summary"] == f"you prefer {phrase}"
    assert payload["data"]["active"] is True
    assert payload["data"]["soft_deleted"] is False


def test_remember_response_includes_compact_receipt() -> None:
    api = client()
    phrase = unique_phrase()
    payload = api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"}).json()
    assert payload["message"] == f"Remembered: you prefer {phrase}."
    assert payload["receipts"][0]["action"] == "brain.memory_remembered"
    assert payload["receipts"][0]["summary"] == f"Remembered: you prefer {phrase}."


def test_retrieve_finds_saved_preference_without_raw_record_dump() -> None:
    api = client()
    phrase = unique_phrase()
    api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"})
    payload = api.post("/api/brain/retrieve", json={"query": "how I like answers", "limit": 3}).json()
    assert payload["status"] == "passed"
    assert phrase in payload["message"]
    assert "brain_mem_" not in payload["message"]
    assert "soft_deleted" not in payload["message"]


def test_missing_retrieval_returns_exact_phrase() -> None:
    payload = client().post("/api/brain/retrieve", json={"query": f"missing {uuid4().hex}", "limit": 3}).json()
    assert payload["message"] == MISS


def test_forget_soft_deletes_memory() -> None:
    api = client()
    phrase = unique_phrase()
    remembered = api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"}).json()
    forgotten = api.post("/api/brain/forget", json={"query": phrase}).json()
    assert forgotten["status"] == "passed"
    assert forgotten["data"]["id"] == remembered["data"]["id"]
    assert forgotten["data"]["soft_deleted"] is True
    assert forgotten["data"]["active"] is False


def test_event_recorded_on_create() -> None:
    api = client()
    phrase = unique_phrase()
    remembered = api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"}).json()
    events = store().list_events(remembered["data"]["id"])
    assert any(event["event_type"] == "created" for event in events)


def test_event_recorded_on_forget() -> None:
    api = client()
    phrase = unique_phrase()
    remembered = api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"}).json()
    api.post("/api/brain/forget", json={"query": phrase})
    events = store().list_events(remembered["data"]["id"])
    assert any(event["event_type"] == "soft_deleted" for event in events)


def test_forgotten_memory_is_not_retrieved() -> None:
    api = client()
    phrase = unique_phrase()
    api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"})
    api.post("/api/brain/forget", json={"query": phrase})
    retrieved = api.post("/api/brain/retrieve", json={"query": phrase, "limit": 3}).json()
    assert retrieved["message"] == MISS


def test_active_focus_can_be_set() -> None:
    payload = client().post("/api/brain/focus", json={"focus": "Brain V1 Batch 1", "session_id": "sess_focus_test"}).json()
    assert payload["status"] == "passed"
    assert payload["data"]["focus"] == "Brain V1 Batch 1"


def test_current_work_question_answers_from_active_focus() -> None:
    api = client()
    session_id = f"sess_{uuid4().hex[:8]}"
    api.post("/api/chat", json={"session_id": session_id, "message": "update your focus to Brain V1 Batch 1"})
    payload = api.post("/api/chat", json={"session_id": session_id, "message": "what are we currently working on?"}).json()
    assert payload["data"]["assistant_message"]["content"] == "We are currently working on: Brain V1 Batch 1."


def test_active_focus_persists_after_store_reinitialization() -> None:
    settings = make_settings()
    api = client(settings)
    session_id = f"sess_{uuid4().hex[:8]}"
    api.post("/api/brain/focus", json={"focus": "Brain V1 Batch 1", "session_id": session_id})
    reloaded = BrainMemoryStore(settings.database_url)
    focus = reloaded.status()["active_focus"]
    assert focus == "Brain V1 Batch 1"


def test_memory_persists_after_store_reinitialization() -> None:
    settings = make_settings()
    phrase = unique_phrase()
    client(settings).post("/api/brain/remember", json={"content": f"I prefer {phrase}"})
    reloaded = BrainMemoryStore(settings.database_url)
    assert any(phrase in item["summary"] for item in reloaded.search(phrase))


def test_global_memory_disabled_blocks_writes() -> None:
    settings = make_settings()
    settings.brain_memory_global_enabled = False
    payload = client(settings).post("/api/brain/remember", json={"content": f"I prefer {unique_phrase()}"}).json()
    assert payload["status"] == "disabled"
    assert payload["data"] is None
    assert payload["message"] == "Global Brain memory writes are disabled."


def test_project_memory_disabled_blocks_project_writes() -> None:
    settings = make_settings()
    settings.brain_memory_project_enabled = False
    payload = client(settings).post("/api/brain/remember", json={"content": f"I prefer {unique_phrase()}", "project_scope": "x8"}).json()
    assert payload["status"] == "disabled"
    assert payload["message"] == "Project Brain memory writes are disabled."


def test_session_memory_disabled_blocks_session_writes() -> None:
    settings = make_settings()
    settings.brain_memory_session_enabled = False
    payload = client(settings).post("/api/brain/remember", json={"content": f"I prefer {unique_phrase()}", "session_scope": "sess_disabled"}).json()
    assert payload["status"] == "disabled"
    assert payload["message"] == "Session Brain memory writes are disabled."


def test_token_memory_is_blocked() -> None:
    payload = client().post("/api/brain/remember", json={"content": "my GitHub token is ghp_abc123"}).json()
    assert payload["status"] == "blocked"
    assert payload["data"] is None
    assert "ghp_abc123" not in str(payload)


def test_password_memory_is_blocked() -> None:
    payload = client().post("/api/brain/remember", json={"content": "my password is hunter2"}).json()
    assert payload["status"] == "blocked"
    assert payload["data"] is None
    assert "hunter2" not in str(payload)


def test_private_key_memory_is_blocked() -> None:
    payload = client().post("/api/brain/remember", json={"content": "private key -----BEGIN PRIVATE KEY----- abc"}).json()
    assert payload["status"] == "blocked"
    assert payload["data"] is None
    assert "BEGIN PRIVATE KEY" not in str(payload)


def test_blocked_secret_is_not_echoed_or_stored() -> None:
    api = client()
    token = f"ghp_{uuid4().hex}abc"
    payload = api.post("/api/brain/remember", json={"content": f"my GitHub token is {token}"}).json()
    memories = api.get("/api/brain/memories").json()
    assert token not in str(payload)
    assert token not in str(memories)


def test_blocked_secret_is_not_stored_in_events_or_receipts() -> None:
    api = client()
    token = f"sk-{uuid4().hex}"
    payload = api.post("/api/brain/remember", json={"content": f"my api key is {token}"}).json()
    events = store().list_events()
    assert token not in str(payload["receipts"])
    assert token not in str(events)


def test_sensitive_personal_memory_is_approval_gated() -> None:
    phrase = f"my family history includes {uuid4().hex[:8]}"
    payload = client().post("/api/brain/remember", json={"content": phrase}).json()
    assert payload["status"] == "approval_required"
    assert payload["data"]["requires_approval"] is True
    assert payload["data"]["active"] is False
    assert payload["message"] == "That memory needs approval before I save it."


def test_pending_memory_is_not_retrieved_until_approved() -> None:
    api = client()
    phrase = f"my family history includes phase2 {uuid4().hex[:8]}"
    pending = api.post("/api/brain/remember", json={"content": phrase}).json()["data"]
    miss = api.post("/api/brain/retrieve", json={"query": phrase}).json()
    assert miss["message"] == MISS
    approved = api.post(f"/api/brain/memories/{pending['id']}/approve").json()
    assert approved["status"] == "approved"
    found = api.post("/api/brain/retrieve", json={"query": phrase}).json()
    assert "family history" in found["message"]


def test_reject_pending_memory_keeps_it_out_of_retrieval() -> None:
    api = client()
    phrase = f"my family history includes reject {uuid4().hex[:8]}"
    pending = api.post("/api/brain/remember", json={"content": phrase}).json()["data"]
    rejected = api.post(f"/api/brain/memories/{pending['id']}/reject").json()
    assert rejected["status"] == "rejected"
    assert api.post("/api/brain/retrieve", json={"query": phrase}).json()["message"] == MISS


def test_policy_safe_update_blocks_secret_content() -> None:
    api = client()
    record = api.post("/api/brain/remember", json={"content": f"I prefer {unique_phrase()}"}).json()["data"]
    token = f"ghp_{uuid4().hex}abc"
    blocked = api.patch(f"/api/brain/memories/{record['id']}", json={"content": f"token is {token}"}).json()
    assert blocked["status"] == "blocked"
    assert token not in str(blocked)


def test_memory_list_filters_pending_records() -> None:
    api = client()
    phrase = f"my family history includes pending list {uuid4().hex[:8]}"
    api.post("/api/brain/remember", json={"content": phrase})
    pending = api.get("/api/brain/memories?status_filter=pending").json()
    assert any(phrase in item["summary"] for item in pending["data"])


def test_memory_routes_return_stable_json() -> None:
    api = client()
    status = api.get("/api/brain/status").json()
    memories = api.get("/api/brain/memories").json()
    assert {"brain_ready", "active_memory_count", "pending_approval_count", "auto_capture_enabled", "global_memory_enabled", "project_memory_enabled", "session_memory_mode", "reads_allowed", "writes_allowed", "storage_backend"} <= set(status["data"])
    assert status["data"]["storage_backend"] == "postgres"
    assert isinstance(memories["data"], list)


def test_chat_routes_explicit_remember_command_to_brain() -> None:
    phrase = unique_phrase()
    payload = client().post("/api/chat", json={"message": f"remember that I prefer {phrase}"}).json()
    assert payload["data"]["assistant_message"]["content"] == f"Remembered: you prefer {phrase}."
    assert payload["data"]["assistant_message"]["cards"][0]["payload"]["provider"] == "brain"


def test_chat_routes_retrieve_command_to_brain() -> None:
    api = client()
    phrase = unique_phrase()
    api.post("/api/chat", json={"message": f"remember that I prefer {phrase}"})
    payload = api.post("/api/chat", json={"message": "what do you remember about how I like answers?"}).json()
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "brain_retrieve"
    assert payload["data"]["assistant_message"]["cards"][0]["title"] == "Memory used"
    assert payload["data"]["assistant_message"]["cards"][0]["payload"]["auto_capture"] is False
    assert phrase in payload["data"]["assistant_message"]["content"]


def test_chat_routes_forget_command_to_brain() -> None:
    api = client()
    phrase = unique_phrase()
    api.post("/api/chat", json={"message": f"remember that I prefer {phrase}"})
    payload = api.post("/api/chat", json={"message": f"forget that I prefer {phrase}"}).json()
    assert payload["data"]["assistant_message"]["content"] == f"Forgotten: you prefer {phrase}."


def test_chat_routes_active_focus_update_to_brain() -> None:
    payload = client().post("/api/chat", json={"message": "update your focus to Brain V1 Batch 1"}).json()
    assert payload["data"]["assistant_message"]["content"] == "Focus updated: Brain V1 Batch 1."
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "brain_focus_update"


def test_github_prompt_still_routes_to_github() -> None:
    payload = client().post("/api/chat", json={"message": "check github status"}).json()
    assert payload["data"]["assistant_message"]["content"] == "GitHub status loaded without mutation."
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "github_status"


def test_self_build_prompt_still_routes_to_self_build() -> None:
    payload = client().post("/api/chat", json={"message": "self-build proposal for README"}).json()
    assert payload["data"]["assistant_message"]["content"] == "Self-build prompt detected. Patch proposal requires approval before apply."
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "self_build"


def test_hello_still_bypasses_model() -> None:
    payload = client().post("/api/chat", json={"message": "hello"}).json()
    assert payload["data"]["assistant_message"]["content"] == "Hello. I'm XV8."
    assert payload["status"] == "passed"


def test_normal_model_backed_chat_still_uses_model_when_available(tmp_path) -> None:
    class Adapter:
        def models(self):
            return True, ["qwen3:8b"], ""

        def generate(self, model: str, prompt: str):
            return True, "mock model response", ""

    kernel = XV8Kernel(
        KernelContextAssembler(BrainContextAssembler(str(tmp_path), {"context_max_messages": 2, "context_max_attachment_chars": 20, "context_max_memory_items": 5, "context_max_knowledge_items": 1}), KernelPromptBuilder()),
        ModelRouter(Adapter(), ModelProfileManager("qwen3:8b", "")),  # type: ignore[arg-type]
    )
    response = kernel.handle(KernelRequest(session_id="sess_model", user_message="give me six sentences about memory"))
    assert response.assistant_message == "mock model response"
    assert response.receipt.status == "passed"


def test_low_risk_preference_auto_saves_from_chat() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    phrase = f"phase3 direct senior-engineer answers {uuid4().hex[:8]}"
    payload = api.post("/api/chat", json={"message": f"I prefer {phrase}."}).json()
    assert any(receipt["action"] == "brain.memory_auto_saved" for receipt in payload["receipts"])
    assert any(card["title"] == "Memory saved" for card in payload["data"]["assistant_message"]["cards"])
    memories = api.get(f"/api/brain/memories?q={phrase}").json()
    assert sum(1 for item in memories["data"] if phrase in item["summary"] and item["active"]) == 1


def test_repeated_low_risk_preference_does_not_duplicate() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    phrase = f"phase3 duplicate direct answers {uuid4().hex[:8]}"
    api.post("/api/chat", json={"message": f"I prefer {phrase}."})
    duplicate = api.post("/api/chat", json={"message": f"I prefer {phrase}."}).json()
    memories = api.get(f"/api/brain/memories?q={phrase}").json()["data"]
    candidates = api.get("/api/brain/candidates?decision=duplicate").json()["data"]
    assert sum(1 for item in memories if phrase in item["summary"] and item["active"]) == 1
    assert any("Already remembered" in receipt["summary"] for receipt in duplicate["receipts"])
    assert any(candidate["decision"] == "duplicate" for candidate in candidates)


def test_correction_updates_existing_memory_and_records_event() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    marker = uuid4().hex[:8]
    api.post("/api/chat", json={"message": f"I prefer verbose phase3 answers {marker}."})
    payload = api.post("/api/chat", json={"message": f"Actually, I prefer short direct answers unless we are debugging {marker}."}).json()
    memories = api.get(f"/api/brain/memories?q={marker}").json()["data"]
    events = api.get("/api/brain/events?event_type=correction_applied").json()["data"]
    assert any(receipt["action"] == "brain.memory_correction_applied" for receipt in payload["receipts"])
    assert any("short direct answers" in item["summary"] for item in memories)
    assert any(marker in event["event_summary"] for event in events)


def test_active_work_context_auto_saves_and_updates_focus() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    marker = uuid4().hex[:8]
    api.post("/api/chat", json={"message": f"We are working on Brain V1 Phase 3 {marker}."})
    status = api.get("/api/brain/status").json()["data"]
    assert marker in status["active_focus"]
    assert status["latest_auto_capture_event"]["decision"] == "auto_save"


def test_validation_checkpoint_auto_saves() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    marker = uuid4().hex[:8]
    api.post("/api/chat", json={"message": f"api-tests passed: 115 passed, 1 warning {marker}"})
    memories = api.get(f"/api/brain/memories?q={marker}").json()["data"]
    assert any(item["type"] == "validation_checkpoint" for item in memories)


def test_sensitive_auto_capture_becomes_pending_approval() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    phrase = f"my family history includes phase3 pending {uuid4().hex[:8]}"
    payload = api.post("/api/chat", json={"message": phrase}).json()
    pending = api.get("/api/brain/memories?status_filter=pending").json()["data"]
    assert any(receipt["action"] == "brain.memory_candidate_pending" for receipt in payload["receipts"])
    assert any(phrase in item["summary"] for item in pending)


def test_secret_auto_capture_is_blocked_and_redacted() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    token = f"ghp_{uuid4().hex}abc"
    payload = api.post("/api/chat", json={"message": f"my GitHub token is {token}"}).json()
    candidates = api.get("/api/brain/candidates?decision=blocked").json()["data"]
    events = api.get("/api/brain/events").json()["data"]
    assert any(receipt["action"] == "brain.memory_candidate_blocked" for receipt in payload["receipts"])
    assert token not in str(payload)
    assert token not in str(candidates)
    assert token not in str(events)


def test_auto_capture_disabled_prevents_auto_save_but_manual_remember_works() -> None:
    api = client()
    phrase = f"phase3 disabled auto {uuid4().hex[:8]}"
    api.post("/api/brain/auto-capture/toggle", json={"enabled": False})
    payload = api.post("/api/chat", json={"message": f"I prefer {phrase}."}).json()
    memories = api.get(f"/api/brain/memories?q={phrase}").json()["data"]
    manual = api.post("/api/brain/remember", json={"content": f"I prefer manual {phrase}"}).json()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    assert not any(receipt["action"].startswith("brain.memory_auto") for receipt in payload["receipts"])
    assert not memories
    assert manual["status"] == "passed"


def test_max_candidates_per_turn_enforced() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    marker = uuid4().hex[:8]
    message = "\n".join([f"I prefer phase3 max {index} {marker}." for index in range(5)])
    payload = api.post("/api/chat", json={"message": message}).json()
    memory_receipts = [receipt for receipt in payload["receipts"] if receipt["action"] == "brain.memory_auto_saved"]
    assert len(memory_receipts) <= 3


def test_ignored_candidates_do_not_create_visible_receipt() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    payload = api.post("/api/chat", json={"message": "okay"}).json()
    assert not any(str(receipt["action"]).startswith("brain.memory") for receipt in payload["receipts"])
    assert not any(card["title"].startswith("Memory") for card in payload["data"]["assistant_message"]["cards"])


def test_candidate_and_event_filters_work() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    phrase = f"phase3 filter direct answers {uuid4().hex[:8]}"
    api.post("/api/chat", json={"message": f"I prefer {phrase}."})
    candidates = api.get("/api/brain/candidates?decision=auto_save").json()
    events = api.get("/api/brain/events?event_type=auto_saved").json()
    assert candidates["status"] == "ready"
    assert any(phrase in item["summary"] for item in candidates["data"])
    assert any(phrase in item["event_summary"] for item in events["data"])


def test_phase3_github_and_self_build_routes_not_stolen_by_auto_capture() -> None:
    api = client()
    api.post("/api/brain/auto-capture/toggle", json={"enabled": True})
    github = api.post("/api/chat", json={"message": "github status and remember direct answers"}).json()
    self_build = api.post("/api/chat", json={"message": "self-build proposal and I prefer direct answers"}).json()
    assert github["receipts"][0]["metadata"]["kernel_lane"] == "github_status"
    assert self_build["receipts"][0]["metadata"]["kernel_lane"] == "self_build"
    assert not any(receipt["action"] == "brain.memory_auto_saved" for receipt in github["receipts"])
    assert not any(receipt["action"] == "brain.memory_auto_saved" for receipt in self_build["receipts"])


def test_embedding_unavailable_does_not_break_manual_remember() -> None:
    api = client()
    phrase = f"phase4 unavailable {uuid4().hex[:8]}"
    payload = api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"}).json()
    assert payload["status"] == "passed"
    status = api.get("/api/brain/embedding-status").json()
    assert status["status"] == "unavailable"
    assert "embedding" in status["data"]["failure_reason"].lower()


def test_manual_remember_creates_embedding_with_available_client() -> None:
    manager = semantic_manager()
    result = manager.remember(f"I prefer phase4 direct senior-engineer answers {uuid4().hex[:8]}")
    memory_id = result.data["memory"]["id"]
    embedding = manager.store.embedding_for(memory_id)
    assert embedding is not None
    assert embedding["embedding_model"] == "nomic-embed-text:latest"
    assert embedding["vector_dimension"] == 3


def test_auto_saved_and_approved_pending_memories_create_embeddings() -> None:
    manager = semantic_manager()
    auto = manager.auto_capture(f"I prefer phase4 auto direct answers {uuid4().hex[:8]}.", lane="normal_chat")
    assert auto.data["saved"]
    assert manager.store.embedding_for(auto.data["saved"][0]["id"]) is not None
    pending = manager.remember(f"my family history includes phase4 pending {uuid4().hex[:8]}")
    memory_id = pending.data["memory"]["id"]
    assert manager.store.embedding_for(memory_id) is None
    approved = manager.approve(memory_id)
    assert approved.status == "approved"
    assert manager.store.embedding_for(memory_id) is not None


def test_memory_edit_reactivate_and_reindex_update_embeddings() -> None:
    manager = semantic_manager()
    result = manager.remember(f"I prefer phase4 edit direct answers {uuid4().hex[:8]}")
    memory_id = result.data["memory"]["id"]
    before = manager.store.embedding_for(memory_id)
    manager.update_memory(memory_id, {"summary": f"you prefer phase4 routing memory {uuid4().hex[:8]}", "content": "GitHub prompts must not steal self-build routing."})
    after = manager.store.embedding_for(memory_id)
    assert before and after and before["content_hash"] != after["content_hash"]
    manager.store.soft_delete_memory(memory_id)
    assert manager.store.embedding_for(memory_id)["active"] is False
    manager.reactivate(memory_id)
    assert manager.store.embedding_for(memory_id)["active"] is True
    assert manager.reindex().data["indexed"] >= 1


def test_semantic_retrieval_finds_paraphrased_memory_examples() -> None:
    manager = semantic_manager()
    manager.remember(f"I prefer direct senior-engineer answers {uuid4().hex[:8]}")
    manager.remember(f"GitHub prompts must not steal self-build routing {uuid4().hex[:8]}")
    manager.remember(f"Self-build approved apply proof uses runtime/self_build_smoke/approved_apply_proof.md {uuid4().hex[:8]}")
    preference = manager.retrieve("how should you respond to me?")
    routing = manager.retrieve("what was the routing issue we fixed?")
    proof = manager.retrieve("how do we prove self-build apply works?")
    assert preference.data["retrieval_proof"]["retrieval_mode"] == "semantic"
    assert "senior-engineer" in preference.message
    assert "self-build routing" in routing.message
    assert "runtime/self_build_smoke/approved_apply_proof.md" in proof.message


def test_semantic_retrieval_excludes_pending_rejected_deleted_and_secret_records() -> None:
    manager = semantic_manager()
    pending = manager.remember(f"my family history includes phase4 semantic pending {uuid4().hex[:8]}")
    rejected = manager.remember(f"my family history includes phase4 semantic rejected {uuid4().hex[:8]}")
    manager.reject(rejected.data["memory"]["id"])
    deleted = manager.remember(f"I prefer phase4 deleted direct answers {uuid4().hex[:8]}")
    manager.store.soft_delete_memory(deleted.data["memory"]["id"])
    blocked = manager.remember(f"my GitHub token is ghp_{uuid4().hex}abc")
    retrieved = manager.retrieve("family direct token")
    assert pending.data["memory"]["id"] not in retrieved.data["retrieval_proof"]["memory_ids_used"]
    assert rejected.data["memory"]["id"] not in retrieved.data["retrieval_proof"]["memory_ids_used"]
    assert deleted.data["memory"]["id"] not in retrieved.data["retrieval_proof"]["memory_ids_used"]
    assert blocked.status == "blocked"
    assert not any("ghp_" in text for text in manager.embedding_client.calls)


def test_keyword_fallback_and_exact_miss_phrase_when_embedding_unavailable() -> None:
    manager = semantic_manager(available=False)
    marker = uuid4().hex[:8]
    manager.remember(f"I prefer phase4 fallback direct answers {marker}")
    found = manager.retrieve(f"fallback direct answers {marker}")
    missing = manager.retrieve(f"not present {uuid4().hex}")
    assert found.data["retrieval_proof"]["fallback_used"] is True
    assert found.data["retrieval_proof"]["retrieval_mode"] == "keyword"
    assert missing.message == MISS


def test_retrieval_proof_and_embedding_routes_are_stable() -> None:
    api = client()
    phrase = f"phase4 stable direct answers {uuid4().hex[:8]}"
    api.post("/api/brain/remember", json={"content": f"I prefer {phrase}"})
    retrieved = api.post("/api/brain/retrieve", json={"query": phrase}).json()
    status = api.get("/api/brain/embedding-status").json()
    reindex = api.post("/api/brain/reindex").json()
    proof = retrieved["data"]["retrieval_proof"]
    assert {"retrieval_mode", "memory_ids_used", "fallback_used", "fallback_reason", "embedding_available", "embedding_model", "semantic_index_count"} <= set(proof)
    assert "embedding_json" not in str(status)
    assert "embedding_json" not in str(reindex)


def test_phase5_continuity_project_next_blocker_validation_and_decision() -> None:
    api = client()
    marker = uuid4().hex[:8]
    project = api.post("/api/brain/continuity/project-state", json={"summary": f"Brain V1 Phase 5 {marker}", "session_scope": marker}).json()
    next_step = api.post("/api/chat", json={"session_id": marker, "message": f"the next step is Phase 5 validation {marker}"}).json()
    blocker = api.post("/api/chat", json={"session_id": marker, "message": f"the blocker is Docker Desktop is offline {marker}"}).json()
    validation = api.post("/api/chat", json={"session_id": marker, "message": f"we validated Phase 4 with 139 API tests passing {marker}"}).json()
    decision = api.post("/api/chat", json={"session_id": marker, "message": f"decision: continuity records should be structured before calendar automation {marker}"}).json()
    assert project["message"] == f"Saved current project state: Brain V1 Phase 5 {marker}."
    assert next_step["data"]["assistant_message"]["content"] == f"Saved next step: Phase 5 validation {marker}."
    assert blocker["data"]["assistant_message"]["content"] == f"Saved blocker: Docker Desktop is offline {marker}."
    assert validation["data"]["assistant_message"]["content"] == f"Saved validation checkpoint: Phase 4 with 139 API tests passing {marker}."
    assert decision["data"]["assistant_message"]["content"] == f"Saved decision: continuity records should be structured before calendar automation {marker}."
    assert api.post("/api/chat", json={"session_id": marker, "message": "what are we currently working on?"}).json()["data"]["assistant_message"]["content"] == f"Current project state: Brain V1 Phase 5 {marker}."
    assert api.post("/api/chat", json={"session_id": marker, "message": "what is the next step?"}).json()["data"]["assistant_message"]["content"] == f"Next step: Phase 5 validation {marker}."
    assert api.post("/api/chat", json={"session_id": marker, "message": "what is blocked?"}).json()["data"]["assistant_message"]["content"] == f"Current blocker: Docker Desktop is offline {marker}."
    assert api.post("/api/chat", json={"session_id": marker, "message": "what did we validate last?"}).json()["data"]["assistant_message"]["content"] == f"Last validation checkpoint: Phase 4 with 139 API tests passing {marker}."
    assert marker in api.post("/api/chat", json={"session_id": marker, "message": "what did we decide about the brain?"}).json()["data"]["assistant_message"]["content"]


def test_phase5_continuity_tasks_handoff_and_routes_are_stable() -> None:
    api = client()
    marker = uuid4().hex[:8]
    task = api.post("/api/brain/continuity/tasks", json={"summary": f"write Phase 5 tests {marker}", "session_scope": marker}).json()
    assert task["status"] == "passed"
    patched = api.patch(f"/api/brain/continuity/tasks/{task['data']['id']}", json={"status": "done", "active": False}).json()
    archived = api.delete(f"/api/brain/continuity/tasks/{task['data']['id']}").json()
    api.post("/api/chat", json={"session_id": marker, "message": f"we are working on Brain V1 Phase 5 {marker}"})
    api.post("/api/chat", json={"session_id": marker, "message": f"the next step is validation {marker}"})
    api.post("/api/chat", json={"session_id": marker, "message": f"the blocker is no live browser connector {marker}"})
    api.post("/api/chat", json={"session_id": marker, "message": f"we validated API tests {marker}"})
    api.post("/api/chat", json={"session_id": marker, "message": f"decision: brain continuity stays structured {marker}"})
    handoff = api.post("/api/brain/continuity/handoff", json={"session_scope": marker}).json()
    assert patched["data"]["status"] == "done"
    assert archived["data"]["soft_deleted"] is True
    assert "Handoff note:" in handoff["data"]["handoff"]
    assert f"Brain V1 Phase 5 {marker}" in handoff["data"]["handoff"]
    assert f"validation {marker}" in handoff["data"]["handoff"]
    assert f"no live browser connector {marker}" in handoff["data"]["handoff"]


def test_phase5_next_step_updates_without_duplicates_and_blocker_clears() -> None:
    api = client()
    marker = uuid4().hex[:8]
    api.post("/api/chat", json={"session_id": marker, "message": f"the next step is first step {marker}"})
    api.post("/api/chat", json={"session_id": marker, "message": f"the next step is second step {marker}"})
    records = api.get(f"/api/brain/continuity/records?record_type=next_step&session_scope={marker}").json()["data"]
    assert len([item for item in records if item["status"] == "active"]) == 1
    assert records[0]["summary"] == f"second step {marker}"
    api.post("/api/chat", json={"session_id": marker, "message": f"the blocker is blocker {marker}"})
    assert api.post("/api/chat", json={"session_id": marker, "message": "clear the blocker"}).json()["data"]["assistant_message"]["content"] == "Current blocker cleared."
    assert api.post("/api/chat", json={"session_id": marker, "message": "what is blocked?"}).json()["data"]["assistant_message"]["content"] == "I don’t have a blocker saved yet."


def test_phase5_auto_capture_and_secret_blocking_do_not_steal_guarded_routes() -> None:
    api = client()
    marker = uuid4().hex[:8]
    captured = api.post("/api/chat", json={"session_id": marker, "message": f"we are working on captured continuity {marker}"}).json()
    secret = f"ghp_{uuid4().hex}abc"
    blocked = api.post("/api/chat", json={"session_id": marker, "message": f"the blocker is token {secret}"}).json()
    github = api.post("/api/chat", json={"session_id": marker, "message": "github status and the next step is do not steal"}).json()
    self_build = api.post("/api/chat", json={"session_id": marker, "message": "create a self-build proposal to improve continuity routing"}).json()
    memory = api.post("/api/chat", json={"session_id": marker, "message": f"remember that I prefer continuity tests {marker}"}).json()
    assert captured["receipts"][0]["metadata"]["kernel_lane"] == "brain_continuity"
    assert blocked["data"]["assistant_message"]["content"] == "I can’t save secrets or credentials in continuity memory."
    assert secret not in str(blocked)
    assert github["receipts"][0]["metadata"]["kernel_lane"] == "github_status"
    assert self_build["receipts"][0]["metadata"]["kernel_lane"] == "self_build"
    assert memory["receipts"][0]["metadata"]["kernel_lane"] == "brain_remember"
