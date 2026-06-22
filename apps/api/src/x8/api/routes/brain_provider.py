from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["brain-provider"])


@router.get("/brain-provider/ping")
def ping():
    return {"status": "ok"}
