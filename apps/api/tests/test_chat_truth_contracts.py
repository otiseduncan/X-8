from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.kernel.brain_context import BrainContextAssembler
from x8.kernel.contracts import KernelRequest
from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.kernel import XV8Kernel
from x8.kernel.model_router import ModelProfileManager, ModelRouter
from x8.kernel.prompt_builder import KernelPromptBuilder
from x8.managers.model_manager import OllamaAdapter
from x8.settings import Settings


def client() -> TestClient:
    settings = Settings(knowledge_root="/app/knowledge")
    settings.ollama_base_url = "http://127.0.0.1:9"
    settings.default_chat_model = ""
    settings.fallback_chat_model = ""
    settings.code_model = ""
    settings.reasoning_model = ""
    return TestClient(create_app(settings))


def unavailable_kernel(tmp_path, context_max_messages: int = 20) -> XV8Kernel:
    limits = {
        "context_max_messages": context_max_messages,
        "context_max_attachment_chars": 200,
        "context_max_memory_items": 20,
        "context_max_knowledge_items": 20,
    }
    return XV8Kernel(
        KernelContextAssembler(BrainContextAssembler(str(tmp_path), limits), KernelPromptBuilder()),
        ModelRouter(OllamaAdapter("http://127.0.0.1:9"), ModelProfileManager("", "")),
    )


def test_chat_answers_identity_without_model() -> None:
    payload = client().post("/api/chat", json={"message": "what is your name"}).json()
    assert payload["status"] == "passed"
    assert payload["data"]["assistant_message"]["content"] == "My name is XV8."


def test_chat_answers_simple_greeting_without_model_or_limitation_card() -> None:
    payload = client().post("/api/chat", json={"message": "hello"}).json()
    assert payload["status"] == "passed"
    assert payload["data"]["assistant_message"]["content"] == "Hello. I'm XV8."
    assert payload["data"]["assistant_message"]["cards"] == []
    assert "assistant model is unavailable" not in str(payload).lower()


def test_chat_can_say_github_without_capability_denial() -> None:
    payload = client().post("/api/chat", json={"message": "can you say GitHub"}).json()
    content = payload["data"]["assistant_message"]["content"]
    assert payload["status"] == "passed"
    assert content == "GitHub."
    assert "cannot access" not in content.lower()
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "normal_chat"
    assert payload["data"]["assistant_message"]["cards"] == []


def test_chat_github_status_routes_to_github_ops_card() -> None:
    payload = client().post("/api/chat", json={"message": "check GitHub status"}).json()
    cards = payload["data"]["assistant_message"]["cards"]
    assert payload["status"] == "passed"
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "github_status"
    assert cards[0]["title"] == "GitHub Ops status"
    assert cards[0]["payload"]["provider"] == "github_ops"
    assert cards[0]["payload"]["read_only"] is True
    assert "assistant model is unavailable" not in str(payload).lower()


def test_chat_github_create_repo_routes_to_approval_card_without_token_leak() -> None:
    payload = client().post(
        "/api/chat",
        json={"message": "prepare a GitHub create-repo proposal for a private disposable repo named x8-validation-smoke"},
    ).json()
    cards = payload["data"]["assistant_message"]["cards"]
    assert payload["status"] == "passed"
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "github_create_repo"
    assert cards[0]["type"] == "approval"
    assert cards[0]["title"] == "GitHub create-repo"
    assert cards[0]["payload"]["repo_name"] == "x8-validation-smoke"
    assert cards[0]["payload"]["visibility"] == "private"
    assert cards[0]["payload"]["github_write_ran"] is False
    assert "ghp_secret" not in str(payload)
    assert "Authorization" not in str(payload)


def test_chat_github_push_routes_to_preview_and_approval_cards() -> None:
    payload = client().post("/api/chat", json={"message": "push this repo"}).json()
    cards = payload["data"]["assistant_message"]["cards"]
    assert payload["status"] == "passed"
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "github_push"
    assert [card["title"] for card in cards] == ["GitHub push preview", "Push this repo"]
    assert cards[0]["payload"]["github_write_ran"] is False
    assert cards[1]["payload"]["operation"] == "push"
    assert cards[1]["payload"]["approval_required"] is True


def test_chat_github_pull_routes_to_preview_and_approval_cards() -> None:
    payload = client().post("/api/chat", json={"message": "pull latest"}).json()
    cards = payload["data"]["assistant_message"]["cards"]
    assert payload["status"] == "passed"
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "github_pull"
    assert [card["title"] for card in cards] == ["GitHub pull preview", "Pull latest"]
    assert cards[0]["payload"]["github_write_ran"] is False
    assert cards[1]["payload"]["operation"] == "pull"


def test_chat_self_build_github_bug_routes_to_self_build_before_github_or_code_help() -> None:
    payload = client().post("/api/chat", json={"message": "create a self-build proposal to fix a fake GitHub routing bug"}).json()
    cards = payload["data"]["assistant_message"]["cards"]
    assert payload["status"] == "passed"
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "self_build"
    assert cards[0]["title"] == "Self-build prompt detected"
    assert cards[0]["payload"]["provider"] == "self_build"
    assert "assistant model is unavailable" not in str(payload).lower()


def test_kernel_uses_attachment_text_without_model(tmp_path) -> None:
    response = unavailable_kernel(tmp_path).handle(
        KernelRequest(
            session_id="sess_test",
            user_message="use this attachment",
            attachments=[{"filename": "notes.txt", "extracted_text": "XV8 is currently repairing attachment context."}],
        )
    )
    assert response.receipt.kernel_lane == "attachment_question"
    assert response.receipt.status == "passed"
    assert "notes.txt: XV8 is currently repairing attachment context." in response.assistant_message
    assert "cannot access" not in response.assistant_message.lower()


def test_kernel_current_work_uses_session_context_without_model(tmp_path) -> None:
    response = unavailable_kernel(tmp_path, context_max_messages=4).handle(
        KernelRequest(
            session_id="sess_test",
            user_message="what are we currently working on",
            session_messages=[
                {"role": "user", "content": "use this attachment"},
                {"role": "assistant", "content": "I can access the uploaded attachment text included in this turn."},
                {"role": "user", "content": "what are we currently working on"},
            ],
        )
    )
    assert response.receipt.status == "passed"
    assert "Current XV8 chat context is based on recent messages:" in response.assistant_message
    assert "- user: use this attachment" in response.assistant_message
    assert "There is no currently logged work" not in response.assistant_message
