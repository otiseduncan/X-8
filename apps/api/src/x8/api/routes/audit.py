from fastapi import APIRouter

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.audit_manager import audit_manager
from x8.managers.operator_manager import OperatorManager

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/audit/receipts", response_model=ResultEnvelope[list[Receipt]])
def receipts() -> ResultEnvelope[list[Receipt]]:
    return ResultEnvelope(ok=True, status="implemented", data=audit_manager.list_receipts(), message="Receipts listed.")


@router.post("/repo/write-probe", response_model=ResultEnvelope[dict[str, bool]])
def write_probe() -> ResultEnvelope[dict[str, bool]]:
    response = OperatorManager().propose_write(approved=False)
    return ResultEnvelope(
        ok=True,
        status="blocked",
        data={"allowed": bool(response.data["allowed"])},
        message=response.message,
        receipts=response.receipts,
    )
