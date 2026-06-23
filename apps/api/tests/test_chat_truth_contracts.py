from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.settings import Settings


def client() -> TestClient:
    return TestClient(create_app(Settings(knowledge_root="/app/knowledge")))


def test_chat_returns_clear_status_for_identity() -> None:
    payload = client().post("/api/chat", json={"message": "what is your name"}).json()
    assert payload["status"] in {"passed", "unavailable"}


def test_chat_returns_clear_status_for_greeting() -> None:
    payload = client().post("/api/chat", json={"message": "hello"}).json()
    assert payload["status"] in {"passed", "unavailable"}


def test_brain_health_endpoint_reports_ownership_contract() -> None:
    payload = client().get("/api/brain/health?probe=false").json()
    assert payload["conversation_memory_source"] == "openwebui"
    assert payload["operator_memory_source"] == "x8_receipts_and_audit_store"
    assert payload["hardcoded_chat_success_allowed"] is False
