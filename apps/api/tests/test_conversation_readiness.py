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


def test_conversation_repair_routes_to_self_build() -> None:
    planner = ResponsePlanner()
    assert planner.classify("fix conversation") == "self_build"
    assert planner.classify("language issues") == "self_build"
    assert planner.classify("expand the system prompt") == "self_build"
    assert planner.classify("fixing X where it can communicate correctly with me") == "self_build"
    assert planner.classify("correct the conversational aspect and let me know when it is ready to pull") == "self_build"


def test_repo_review_routes_to_inspection() -> None:
    planner = ResponsePlanner()
    assert planner.classify("examine the repo") == "repo_inspection"
    assert planner.classify("production ready") == "repo_inspection"
    assert planner.classify("ready to pull") == "github_pull"


def test_chat_conversation_repair_does_not_become_github_pull() -> None:
    payload = client().post(
        "/api/chat",
        json={"message": "correct the conversational aspect so X can communicate correctly with me and let me know when it is ready to pull"},
    ).json()
    cards = payload["data"]["assistant_message"]["cards"]
    assert payload["receipts"][0]["metadata"]["kernel_lane"] == "self_build"
    assert "Pull latest" not in [card["title"] for card in cards]
