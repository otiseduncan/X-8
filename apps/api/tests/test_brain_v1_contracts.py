from uuid import uuid4

from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.settings import Settings


MISS = "I don’t have a saved memory for that yet."


def client() -> TestClient:
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


def test_sensitive_personal_memory_is_approval_gated() -> None:
    phrase = f"my family history includes {uuid4().hex[:8]}"
    payload = client().post("/api/brain/remember", json={"content": phrase}).json()
    assert payload["status"] == "approval_required"
    assert payload["data"] is None
    assert payload["message"] == "That memory needs approval before I save it."


def test_memory_routes_return_stable_json() -> None:
    api = client()
    status = api.get("/api/brain/status").json()
    memories = api.get("/api/brain/memories").json()
    assert {"brain_ready", "active_memory_count", "pending_approval_count", "auto_capture_enabled"} <= set(status["data"])
    assert isinstance(memories["data"], list)


def test_chat_routes_explicit_remember_command_to_brain() -> None:
    phrase = unique_phrase()
    payload = client().post("/api/chat", json={"message": f"remember that I prefer {phrase}"}).json()
    assert payload["data"]["assistant_message"]["content"] == f"Remembered: you prefer {phrase}."
    assert payload["data"]["assistant_message"]["cards"][0]["payload"]["provider"] == "brain"


def test_chat_routes_forget_command_to_brain() -> None:
    api = client()
    phrase = unique_phrase()
    api.post("/api/chat", json={"message": f"remember that I prefer {phrase}"})
    payload = api.post("/api/chat", json={"message": f"forget that I prefer {phrase}"}).json()
    assert payload["data"]["assistant_message"]["content"] == f"Forgotten: you prefer {phrase}."


def test_github_prompt_still_routes_to_github() -> None:
    payload = client().post("/api/chat", json={"message": "check github status"}).json()
    assert payload["data"]["assistant_message"]["content"] == "GitHub status loaded without mutation."
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "github_status"


def test_self_build_prompt_still_routes_to_self_build() -> None:
    payload = client().post("/api/chat", json={"message": "self-build proposal for README"}).json()
    assert payload["data"]["assistant_message"]["content"] == "Self-build prompt detected. Patch proposal requires approval before apply."
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "self_build"
