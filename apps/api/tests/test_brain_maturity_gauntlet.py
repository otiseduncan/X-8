"""Brain Maturity Q&A Gauntlet — automated pytest runner.

Loads tests/fixtures/brain_maturity_qa.json and runs each case through the API.
Scores by: route, status, response_contains, forbidden_contains, trace fields.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from x8.app_factory import create_app
from x8.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_PATH = Path("/app/tests/fixtures/brain_maturity_qa.json")

_CASES: list[dict[str, Any]] = json.loads(FIXTURE_PATH.read_text()) if FIXTURE_PATH.exists() else []


def _client() -> TestClient:
    s = Settings(knowledge_root="/app/knowledge")
    s.ollama_base_url = "http://127.0.0.1:9"
    s.default_chat_model = ""
    s.fallback_chat_model = ""
    s.code_model = ""
    s.reasoning_model = ""
    return TestClient(create_app(s))


def _seed_memory(c: TestClient, seed_text: str) -> str | None:
    resp = c.post("/api/chat", json={"message": f"remember that {seed_text}"}).json()
    return resp.get("data", {}).get("session_id")


def _post(c: TestClient, message: str, session_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"message": message}
    if session_id:
        body["session_id"] = session_id
    return c.post("/api/chat", json=body).json()


def _ids_for_category(cat: str) -> list[str]:
    return [case["id"] for case in _CASES if case.get("category") == cat]


# ---------------------------------------------------------------------------
# Parameterised gauntlet tests
# ---------------------------------------------------------------------------

def _build_gauntlet_params() -> list[tuple[str, dict[str, Any]]]:
    return [(case["id"], case) for case in _CASES]


@pytest.mark.parametrize("case_id,case", _build_gauntlet_params(), ids=[c["id"] for c in _CASES])
def test_brain_maturity_gauntlet(case_id: str, case: dict[str, Any]) -> None:
    c = _client()
    session_id = None

    if case.get("memory_seed"):
        session_id = _seed_memory(c, case["memory_seed"])

    result = _post(c, case["user_message"], session_id)

    if result.get("error"):
        pytest.fail(f"[{case_id}] API error: {result['error']}")

    content: str = result.get("data", {}).get("assistant_message", {}).get("content", "")
    cards: list[dict] = result.get("data", {}).get("assistant_message", {}).get("cards", [])
    trace: dict = result.get("data", {}).get("decision_trace", {})
    receipt_status: str = result.get("status", "")
    lane: str = trace.get("selected_route", "")
    card_titles = [c2.get("title", "") for c2 in cards]
    all_text = content + " " + " ".join(card_titles) + " " + json.dumps(cards)

    failures: list[str] = []

    # Route
    expected_route = case.get("expected_route")
    if expected_route and lane != expected_route:
        failures.append(f"Route: expected '{expected_route}', got '{lane}'")

    # Status (skip 'unavailable' when expected — model may or may not be available)
    expected_status = case.get("expected_status")
    if expected_status and expected_status != "any" and expected_status != "unavailable":
        if receipt_status != expected_status:
            failures.append(f"Status: expected '{expected_status}', got '{receipt_status}'")

    # Expected content
    for needle in case.get("expected_response_contains", []):
        if needle.lower() not in all_text.lower():
            failures.append(f"Missing expected text: '{needle}'. Response: {content[:200]}")

    # Forbidden content
    for bad in case.get("forbidden_response_contains", []):
        if bad.lower() in all_text.lower():
            failures.append(f"Forbidden text present: '{bad}'. Response: {content[:200]}")

    # Decision trace fields
    for field in case.get("expected_decision_trace_fields", []):
        if field not in trace:
            failures.append(f"Trace missing field: '{field}'")

    # No-limitation-card check
    if case.get("category") == "deterministic_no_limitation_card":
        if any("Kernel limitations" in t for t in card_titles):
            failures.append(f"'Kernel limitations' card found on deterministic route '{lane}'")

    if failures:
        lines = "\n".join(f"  - {f}" for f in failures)
        pytest.fail(f"[{case_id}] {case['user_message'][:80]}\n{lines}")


# ---------------------------------------------------------------------------
# Category-targeted subset tests (run with -k category)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case_id,case", [(c["id"], c) for c in _CASES if c.get("category") == "identity_persona"], ids=[c["id"] for c in _CASES if c.get("category") == "identity_persona"])
def test_brain_identity_persona(case_id: str, case: dict[str, Any]) -> None:
    """Identity and persona category subset — fast re-run for Batch A."""
    test_brain_maturity_gauntlet(case_id, case)


@pytest.mark.parametrize("case_id,case", [(c["id"], c) for c in _CASES if c.get("category") in ("memory_capture", "memory_recall", "memory_forget")], ids=[c["id"] for c in _CASES if c.get("category") in ("memory_capture", "memory_recall", "memory_forget")])
def test_brain_memory_maturity(case_id: str, case: dict[str, Any]) -> None:
    """Memory capture/recall/forget subset — fast re-run for Batch C."""
    test_brain_maturity_gauntlet(case_id, case)


@pytest.mark.parametrize("case_id,case", [(c["id"], c) for c in _CASES if c.get("category") in ("active_focus", "communication_style")], ids=[c["id"] for c in _CASES if c.get("category") in ("active_focus", "communication_style")])
def test_brain_focus_and_style(case_id: str, case: dict[str, Any]) -> None:
    """Active focus and communication style subset — Batch D."""
    test_brain_maturity_gauntlet(case_id, case)


@pytest.mark.parametrize("case_id,case", [(c["id"], c) for c in _CASES if c.get("category") == "capability_truth"], ids=[c["id"] for c in _CASES if c.get("category") == "capability_truth"])
def test_brain_capability_truth(case_id: str, case: dict[str, Any]) -> None:
    """Capability truth subset — Batch F."""
    test_brain_maturity_gauntlet(case_id, case)


@pytest.mark.parametrize("case_id,case", [(c["id"], c) for c in _CASES if c.get("category") in ("safety", "operator_blocked")], ids=[c["id"] for c in _CASES if c.get("category") in ("safety", "operator_blocked")])
def test_brain_safety(case_id: str, case: dict[str, Any]) -> None:
    """Safety subset."""
    test_brain_maturity_gauntlet(case_id, case)


@pytest.mark.parametrize("case_id,case", [(c["id"], c) for c in _CASES if c.get("category") == "deterministic_no_limitation_card"], ids=[c["id"] for c in _CASES if c.get("category") == "deterministic_no_limitation_card"])
def test_brain_no_limitation_card_on_deterministic(case_id: str, case: dict[str, Any]) -> None:
    """Deterministic routes must not show Kernel limitations card."""
    test_brain_maturity_gauntlet(case_id, case)
