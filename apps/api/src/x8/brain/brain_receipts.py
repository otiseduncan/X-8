from typing import Any

from x8.contracts.receipts import Receipt


def brain_receipt(action: str, status: str, summary: str, metadata: dict[str, Any] | None = None) -> Receipt:
    return Receipt(action=action, status=status, summary=summary, metadata=metadata or {})


def brain_card(title: str, status: str, summary: str, payload: dict[str, Any] | None = None):
    from x8.kernel.contracts import ResponseCard

    return ResponseCard(type="receipt", title=title, status=status, summary=summary, payload=payload or {})
