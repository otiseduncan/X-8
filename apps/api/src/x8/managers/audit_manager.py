from x8.contracts.receipts import Receipt


class AuditManager:
    name = "audit"
    version = "0.1.0"

    def __init__(self) -> None:
        self._receipts: list[Receipt] = []

    def record(self, receipt: Receipt) -> Receipt:
        self._receipts.append(receipt)
        return receipt

    def list_receipts(self) -> list[Receipt]:
        return list(self._receipts)


audit_manager = AuditManager()
