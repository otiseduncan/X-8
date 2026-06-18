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


def test_chat_can_say_github_without_capability_denial() -> None:
    payload = client().post("/api/chat", json={"message": "can you say GitHub"}).json()
    content = payload["data"]["assistant_message"]["content"]
    assert payload["status"] == "passed"
    assert content == "GitHub."
    assert "cannot access" not in content.lower()


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
