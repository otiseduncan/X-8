from uuid import uuid4

from pydantic import BaseModel

from x8.contracts.receipts import Receipt


class ArtifactPreview(BaseModel):
    id: str
    kind: str
    title: str
    html: str
    css: str
    files: dict[str, str]
    mutated_repo: bool = False
    receipt: Receipt


class ArtifactManager:
    name = "artifact"
    version = "0.1.0"

    def create_html_preview(self, title: str, prompt: str) -> ArtifactPreview:
        artifact_id = f"artifact_{uuid4().hex[:10]}"
        css = "body{margin:0;font-family:Inter,system-ui;background:#111;color:#f8fafc}.hero{padding:48px}.accent{color:#ef4444}"
        html = f"<main class='hero'><p class='accent'>XV8 preview</p><h1>{title}</h1><p>{prompt}</p></main>"
        receipt = Receipt(action="artifact.preview", status="created", summary="Preview artifact created without repo mutation.")
        return ArtifactPreview(
            id=artifact_id,
            kind="html_preview",
            title=title,
            html=html,
            css=css,
            files={"index.html": html, "styles.css": css},
            receipt=receipt,
        )
