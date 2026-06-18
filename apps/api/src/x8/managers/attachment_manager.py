from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from x8.contracts.chat import AttachmentReference, AttachmentUploadReceipt
from x8.storage.postgres_store import PostgresStore


TEXT_EXTENSIONS = {".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".log", ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class AttachmentStorageAdapter:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, attachment_id: str, filename: str, content: bytes) -> str:
        safe_name = Path(filename).name
        target = self.root / f"{attachment_id}_{safe_name}"
        target.write_bytes(content)
        return str(target)


class AttachmentContentExtractor:
    def extract(self, filename: str, content: bytes) -> tuple[bool, str, list[str]]:
        suffix = Path(filename).suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            try:
                return True, content.decode("utf-8")[:20_000], []
            except UnicodeDecodeError:
                return False, "", ["Text file is not valid UTF-8."]
        if suffix in IMAGE_EXTENSIONS:
            return False, "", ["Image stored; image understanding is not active in this chat loop."]
        if suffix == ".pdf":
            return False, "", ["PDF accepted as metadata-only; PDF parsing is not implemented."]
        return False, "", ["Content extraction is unavailable for this file type."]


class AttachmentInspectionManager:
    def __init__(self, allowed_extensions: str, max_mb: int) -> None:
        self.allowed = {item.strip().lower() for item in allowed_extensions.split(",") if item.strip()}
        self.max_bytes = max_mb * 1024 * 1024

    def inspect(self, filename: str, size: int) -> tuple[bool, str]:
        suffix = Path(filename).suffix.lower()
        if suffix not in self.allowed:
            return False, f"{suffix or 'file'} is not an allowed attachment type."
        if size > self.max_bytes:
            return False, f"{filename} is larger than the {self.max_bytes // (1024 * 1024)} MB attachment limit."
        return True, "allowed"


class AttachmentManager:
    def __init__(self, store: PostgresStore, storage: AttachmentStorageAdapter, inspector: AttachmentInspectionManager, extractor: AttachmentContentExtractor) -> None:
        self.store = store
        self.storage = storage
        self.inspector = inspector
        self.extractor = extractor

    async def upload(self, file: UploadFile) -> tuple[AttachmentReference, AttachmentUploadReceipt]:
        content = await file.read()
        attachment_id = f"att_{uuid4().hex[:12]}"
        allowed, reason = self.inspector.inspect(file.filename or "attachment", len(content))
        if not allowed:
            attachment = AttachmentReference(
                attachment_id=attachment_id,
                filename=file.filename or "attachment",
                mime_type=file.content_type or "application/octet-stream",
                size_bytes=len(content),
                status="blocked",
            )
            receipt = AttachmentUploadReceipt(attachment_id=attachment_id, filename=attachment.filename, status="blocked", action_type="attachment_blocked", summary=reason)
            return attachment, receipt
        storage_path = self.storage.write(attachment_id, file.filename or "attachment", content)
        extractable, text, limitations = self.extractor.extract(file.filename or "attachment", content)
        status = "uploaded" if extractable else "attached"
        attachment = AttachmentReference(
            attachment_id=attachment_id,
            filename=file.filename or "attachment",
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            status=status,
            extracted_text=text,
            content_extractable=extractable,
            storage_path=storage_path,
        )
        self.store.insert_attachment(attachment.model_dump())
        action = "attachment_extracted" if extractable else "attachment_unreadable"
        receipt = AttachmentUploadReceipt(attachment_id=attachment_id, filename=attachment.filename, status=status, action_type=action, summary=f"{attachment.filename} stored in runtime attachment storage.", limitations=limitations)
        return attachment, receipt

    def get(self, attachment_id: str) -> AttachmentReference | None:
        row = self.store.get_attachment(attachment_id)
        return AttachmentReference(**row) if row else None
