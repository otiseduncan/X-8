from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.kernel.brain_context import BrainContextAssembler
from x8.kernel.contracts import KernelRequest
from x8.kernel.context_assembler import KernelContextAssembler
from x8.kernel.kernel import XV8Kernel
from x8.kernel.model_router import ModelProfileManager, ModelRouter
from x8.kernel.prompt_builder import KernelPromptBuilder
from x8.managers.model_manager import OllamaAdapter
from x8.managers.memory_manager import MemoryManager, MemoryProposal
from x8.project_builder.manager import ProjectBuilderManager
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
        project_builder_manager=ProjectBuilderManager(str(tmp_path), str(tmp_path / "runtime" / "generated-projects")),
    )


def memory_kernel(tmp_path, memory_manager: MemoryManager, session_messages: list[dict[str, object]] | None = None) -> KernelRequest:
    return KernelRequest(session_id="sess_test", user_message="", session_messages=session_messages or [])


def test_chat_answers_identity_without_model() -> None:
    payload = client().post("/api/chat", json={"message": "what is your name"}).json()
    assert payload["status"] == "passed"
    assert "X" in payload["data"]["assistant_message"]["content"]
    assert "ChatGPT" not in payload["data"]["assistant_message"]["content"]


def test_chat_answers_simple_greeting_without_model_or_limitation_card() -> None:
    payload = client().post("/api/chat", json={"message": "hello"}).json()
    assert payload["status"] == "passed"
    content = payload["data"]["assistant_message"]["content"]
    assert "X" in content
    assert payload["data"]["assistant_message"]["cards"] == []
    assert "assistant model is unavailable" not in str(payload).lower()
    assert "Kernel limitations" not in str(payload)


def test_chat_email_request_returns_draft_only_boundary() -> None:
    payload = client().post("/api/chat", json={"message": "write and send an email to the team"}).json()
    content = payload["data"]["assistant_message"]["content"].lower()
    assert payload["status"] == "passed"
    assert "draft" in content
    assert "cannot send email" in content


def test_chat_sms_request_returns_draft_only_boundary() -> None:
    payload = client().post("/api/chat", json={"message": "send sms to everyone"}).json()
    content = payload["data"]["assistant_message"]["content"].lower()
    assert payload["status"] == "passed"
    assert "draft" in content
    assert "cannot send text" in content


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


def test_chat_response_includes_required_decision_trace_fields() -> None:
    payload = client().post("/api/chat", json={"message": "open README.md"}).json()
    trace = payload["data"]["decision_trace"]
    required = {
        "message_id",
        "user_input_summary",
        "detected_speech_act",
        "selected_route",
        "route_confidence",
        "input_constraints_detected",
        "memories_retrieved",
        "memories_used",
        "memories_rejected",
        "active_focus_used",
        "current_instruction_overrides",
        "capability_status_checked",
        "action_selected",
        "safety_boundary_applied",
        "fallback_used",
        "fallback_reason",
        "final_response_type",
        "receipt_id",
    }
    assert required <= set(trace)
    assert trace["selected_route"] == "repo_inspection"
    assert trace["detected_speech_act"] == "action_request"
    assert "readme_mentioned" in trace["input_constraints_detected"]


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


def test_input_constraints_change_routes_and_readme_mentions_do_not_force_file_viewer(tmp_path) -> None:
    kernel = unavailable_kernel(tmp_path)
    preview = kernel.handle(KernelRequest(session_id="sess_test", user_message="Build a website preview only. Do not write files."))
    write = kernel.handle(KernelRequest(session_id="sess_test", user_message="Create a project that includes README.md using your Project Builder. I approve writing only inside the sandbox/project output path. Use the project folder name: comm-trace-shop"))
    read = kernel.handle(KernelRequest(session_id="sess_test", user_message="Open README.md"))
    assert preview.receipt.kernel_lane == "artifact_preview"
    assert "No files will be written" in preview.assistant_message
    assert write.receipt.kernel_lane == "project_builder"
    assert "Project Builder wrote" in write.assistant_message
    assert read.receipt.kernel_lane == "repo_inspection"


def test_memory_influences_relevant_ui_question_without_raw_dump(tmp_path) -> None:
    memory = MemoryManager(str(tmp_path / "memory.json"))
    record, receipt = memory.propose(MemoryProposal(memory_type="project_fact", source="user_explicit", text="Otis prefers dark UI with red/cyan accents and compact receipts.", confidence=0.95))
    assert record is not None
    if record.status != "active":
        memory.approve(type("Decision", (), {"memory_record_id": record.memory_record_id, "decision": "approve"})())
    limits = {"context_max_messages": 4, "context_max_attachment_chars": 200, "context_max_memory_items": 5, "context_max_knowledge_items": 0}
    kernel = XV8Kernel(
        KernelContextAssembler(BrainContextAssembler(str(tmp_path), limits, memory), KernelPromptBuilder()),
        ModelRouter(OllamaAdapter("http://127.0.0.1:9"), ModelProfileManager("", "")),
    )
    response = kernel.handle(KernelRequest(session_id="sess_test", user_message="What style should this shop dashboard UI use?"))
    assert response.receipt.status == "passed"
    assert "dark UI with red/cyan accents and compact receipts" in response.assistant_message
    assert "project_fact [user_explicit" not in response.assistant_message


def test_irrelevant_memory_is_not_forced_into_unrelated_response(tmp_path) -> None:
    memory = MemoryManager(str(tmp_path / "memory.json"))
    memory.propose(MemoryProposal(memory_type="project_fact", source="user_explicit", text="Otis likes grape soda on Fridays.", confidence=0.95))
    limits = {"context_max_messages": 4, "context_max_attachment_chars": 200, "context_max_memory_items": 5, "context_max_knowledge_items": 0}
    kernel = XV8Kernel(
        KernelContextAssembler(BrainContextAssembler(str(tmp_path), limits, memory), KernelPromptBuilder()),
        ModelRouter(OllamaAdapter("http://127.0.0.1:9"), ModelProfileManager("", "")),
    )
    response = kernel.handle(KernelRequest(session_id="sess_test", user_message="What is your name?"))
    assert "X" in response.assistant_message
    assert "ChatGPT" not in response.assistant_message
    assert "grape soda" not in response.assistant_message


def test_correction_changes_generate_vs_build_behavior(tmp_path) -> None:
    correction = "That is wrong. When I say generate a website, I mean preview only. When I say build/write/create, I mean sandbox files."
    kernel = unavailable_kernel(tmp_path)
    generate = kernel.handle(KernelRequest(session_id="sess_test", user_message="Generate a website for a shop dashboard.", session_messages=[{"role": "user", "content": correction}]))
    build = kernel.handle(KernelRequest(session_id="sess_test", user_message="Build the approved version into the sandbox.", session_messages=[{"role": "user", "content": correction}]))
    assert "generate means preview only" in generate.assistant_message
    assert "build/write/create means approved sandbox files" in build.assistant_message


def test_current_instruction_override_and_safety_boundary_trace() -> None:
    api = client()
    override = api.post("/api/chat", json={"message": "Old memory says always preview first. For this one, I approve writing directly to sandbox with Project Builder."}).json()["data"]["decision_trace"]
    blocked = api.post("/api/chat", json={"message": "Run this shell command and commit and push everything."}).json()["data"]["decision_trace"]
    assert "current_instruction_overrides_memory" in override["current_instruction_overrides"]
    assert "explicit_sandbox_approval" in override["current_instruction_overrides"]
    assert blocked["selected_route"] == "github_push" or blocked["selected_route"] == "operator_blocked"
    assert blocked["safety_boundary_applied"]["requires_approval"] is True or blocked["safety_boundary_applied"]["allowed"] is False


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
    assert "Current session context is based on recent messages:" in response.assistant_message
    assert "- user: use this attachment" in response.assistant_message
    assert "There is no currently logged work" not in response.assistant_message
