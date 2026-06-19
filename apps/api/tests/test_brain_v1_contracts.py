from uuid import uuid4

from fastapi.testclient import TestClient

from x8.app_factory import create_app
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
