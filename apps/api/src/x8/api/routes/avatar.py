from fastapi import APIRouter, Request

from x8.contracts.avatar import AvatarManifest, AvatarState, AvatarStatus
from x8.contracts.base import ResultEnvelope
from x8.contracts.receipts import Receipt
from x8.managers.avatar_manager import AvatarAssetImportManager, AvatarManager

router = APIRouter(prefix="/api/avatar", tags=["avatar"])


@router.get("/manifest", response_model=ResultEnvelope[AvatarManifest])
def manifest() -> ResultEnvelope[AvatarManifest]:
    data = AvatarManager().manifest()
    return ResultEnvelope(ok=True, status=data.status, data=data, message=data.reason)


@router.get("/state", response_model=ResultEnvelope[AvatarState])
def state() -> ResultEnvelope[AvatarState]:
    return ResultEnvelope(ok=True, status="implemented", data=AvatarManager().state(), message="Avatar state loaded.")


@router.get("/status", response_model=ResultEnvelope[AvatarStatus])
def status() -> ResultEnvelope[AvatarStatus]:
    data = AvatarManager().status()
    return ResultEnvelope(ok=True, status=data.status, data=data, message="Avatar status loaded.")


@router.post("/import-x7", response_model=ResultEnvelope[AvatarManifest])
def import_x7(request: Request) -> ResultEnvelope[AvatarManifest]:
    manifest_data, receipt = AvatarAssetImportManager(request.app.state.settings.x7_import_root).import_assets()
    common = Receipt(action="avatar.import_x7", status=receipt.status, summary=f"Imported {receipt.assets_imported} avatar assets.", metadata=receipt.model_dump())
    return ResultEnvelope(ok=True, status=manifest_data.status, data=manifest_data, message=manifest_data.reason, receipts=[common])
