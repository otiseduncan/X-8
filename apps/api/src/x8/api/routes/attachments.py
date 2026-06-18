from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from x8.contracts.base import ResultEnvelope
from x8.contracts.chat import AttachmentReference
from x8.contracts.receipts import Receipt
from x8.managers.attachment_manager import AttachmentContentExtractor, AttachmentInspectionManager, AttachmentManager, AttachmentStorageAdapter
from x8.storage.postgres_store import PostgresStore

router = APIRouter(prefix="/api", tags=["attachments"])


def _manager(request: Request) -> AttachmentManager:
    settings = request.app.state.settings
    store = PostgresStore(settings.database_url)
    return AttachmentManager(
        store,
        AttachmentStorageAdapter(settings.attachment_storage_path),
        AttachmentInspectionManager(settings.attachment_allowed_extensions, settings.attachment_max_mb),
        AttachmentContentExtractor(),
    )


@router.post("/attachments", response_model=ResultEnvelope[AttachmentReference])
async def upload_attachment(request: Request, file: UploadFile = File(...)) -> ResultEnvelope[AttachmentReference]:
    settings = request.app.state.settings
    store = PostgresStore(settings.database_url)
    manager = _manager(request)
    attachment, upload_receipt = await manager.upload(file)
    store.insert_receipt(
        {
            "receipt_id": upload_receipt.receipt_id,
            "action_type": upload_receipt.action_type,
            "status": upload_receipt.status,
            "limitations": upload_receipt.limitations,
            "metadata": {"attachment_id": upload_receipt.attachment_id, "filename": upload_receipt.filename},
        }
    )
    receipt = Receipt(
        id=upload_receipt.receipt_id,
        action=upload_receipt.action_type,
        status=upload_receipt.status,
        summary=upload_receipt.summary,
        metadata={"attachment_id": upload_receipt.attachment_id, "limitations": upload_receipt.limitations},
    )
    return ResultEnvelope(
        ok=attachment.status != "blocked",
        status=attachment.status,
        data=attachment,
        message=upload_receipt.summary,
        receipts=[receipt],
    )


@router.get("/attachments/{attachment_id}", response_model=ResultEnvelope[AttachmentReference])
def get_attachment(attachment_id: str, request: Request) -> ResultEnvelope[AttachmentReference]:
    attachment = _manager(request).get(attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return ResultEnvelope(ok=True, status=attachment.status, data=attachment, message=f"{attachment.filename} loaded.")
