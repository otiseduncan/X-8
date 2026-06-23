from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.settings import Settings


def test_brain_health_declares_memory_ownership():
    client = TestClient(create_app(Settings(knowledge_root="/app/knowledge")))
    payload = client.get("/api/brain/health?probe=false").json()
    assert payload["conversation_memory_source"] == "openwebui"
    assert payload["operator_memory_source"] == "x8_receipts_and_audit_store"
    assert payload["hardcoded_chat_success_allowed"] is False
