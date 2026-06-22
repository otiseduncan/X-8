from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["brain-provider"])


@router.get("/brain-provider/status")
def status():
    return {"status": "ok"}
