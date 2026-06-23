from fastapi import APIRouter

from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.visual_git_proof_lab import run_visual_git_proof_lab

router = APIRouter(prefix="/api/visual-proof-lab", tags=["visual-proof-lab"])


@router.post("/prepare")
def prepare() -> ResultEnvelope[dict[str, str]]:
    result = run_visual_git_proof_lab("Run the visual X8 git proof lab")
    receipt = Receipt(action="visual_git_proof_lab_prepare", status=result.status, summary="Visual proof lab local write staged.")
    return ResultEnvelope(ok=result.status in {"passed", "awaiting_approval"}, status=result.status, message=result.message, data={"message": result.message}, receipts=[receipt])


@router.post("/approve-push")
def approve_push() -> ResultEnvelope[dict[str, str]]:
    result = run_visual_git_proof_lab("Approve visual X8 git proof lab push")
    receipt = Receipt(action="visual_git_proof_lab_initial_push", status=result.status, summary="Visual proof lab initial push attempted.")
    return ResultEnvelope(ok=result.status == "passed", status=result.status, message=result.message, data={"message": result.message}, receipts=[receipt])


@router.post("/approve-repair-push")
def approve_repair_push() -> ResultEnvelope[dict[str, str]]:
    result = run_visual_git_proof_lab("Approve visual X8 git proof lab repair push")
    receipt = Receipt(action="visual_git_proof_lab_repair_push", status=result.status, summary="Visual proof lab repair push attempted.")
    return ResultEnvelope(ok=result.status == "passed", status=result.status, message=result.message, data={"message": result.message}, receipts=[receipt])
