from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.kernel.response_planner import ResponsePlanner
from x8.settings import Settings


def client() -> TestClient:
    settings = Settings(knowledge_root="/app/knowledge")
    settings.ollama_base_url = "http://127.0.0.1:9"
    settings.default_chat_model = ""
    settings.fallback_chat_model = ""
    settings.code_model = ""
    settings.reasoning_model = ""
    return TestClient(create_app(settings))


def test_conversation_repair_routes_to_conversational_lane() -> None:
    planner = ResponsePlanner()
    assert planner.classify("fix conversation") == "conversation_repair"
    assert planner.classify("language issues") == "conversation_repair"
    assert planner.classify("expand the system prompt") == "conversation_repair"
    assert planner.classify("fixing X where it can communicate correctly with me") == "conversation_repair"
    assert planner.classify("correct the conversational aspect and let me know when it is ready to pull") == "conversation_repair"


def test_self_build_still_requires_explicit_patch_language() -> None:
    planner = ResponsePlanner()
    assert planner.classify("create a self-build proposal to fix GitHub push") == "self_build"
    assert planner.classify("apply self-build") == "self_build"
    assert planner.classify("patch proposal") == "self_build"


def test_repo_review_routes_to_inspection() -> None:
    planner = ResponsePlanner()
    assert planner.classify("examine the repo") == "repo_inspection"
    assert planner.classify("production ready") == "repo_inspection"
    assert planner.classify("ready to pull") == "github_pull"


def test_chat_conversation_repair_does_not_become_github_pull_or_self_build() -> None:
    payload = client().post(
        "/api/chat",
        json={"message": "correct the conversational aspect so X can communicate correctly with me and let me know when it is ready to pull"},
    ).json()
    cards = payload["data"]["assistant_message"]["cards"]
    card_titles = [card["title"] for card in cards]
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "conversation_repair"
    assert "Pull latest" not in card_titles
    assert "Self-build patch proposal" not in card_titles
