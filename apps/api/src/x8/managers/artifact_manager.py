import re
from html import escape
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
    version = "0.2.0"

    def create_html_preview(self, title: str, prompt: str) -> ArtifactPreview:
        artifact_id = f"artifact_{uuid4().hex[:10]}"
        site_name = self._infer_site_name(title, prompt)
        palette = self._infer_palette(prompt)
        safe_prompt = escape(prompt.strip())
        safe_site_name = escape(site_name)
        css = self._build_css(palette)
        html = f"""
<main class="site-shell">
  <nav class="topbar">
    <strong>{safe_site_name}</strong>
    <span>Fresh service · Fast response · Local business</span>
  </nav>
  <section class="hero">
    <p class="eyebrow">XV8 live artifact preview</p>
    <h1>{safe_site_name}</h1>
    <p class="lead">{safe_prompt}</p>
    <div class="hero-actions">
      <a href="#contact" class="button primary">Request service</a>
      <a href="#menu" class="button secondary">View highlights</a>
    </div>
  </section>
  <section class="feature-grid" id="menu">
    <article><h2>Built for attention</h2><p>Bold color, clear sections, and strong calls to action.</p></article>
    <article><h2>Customer-ready</h2><p>Simple copy blocks that can be edited into final business content.</p></article>
    <article><h2>Preview first</h2><p>This is a chat preview only. Writing/exporting files still requires approval.</p></article>
  </section>
  <section class="contact" id="contact">
    <h2>Ready to connect?</h2>
    <p>Replace this section with the business phone, email, hours, and service area before publishing.</p>
  </section>
</main>
""".strip()
        receipt = Receipt(action="artifact.preview", status="created", summary="Rich HTML preview artifact created without repo mutation.")
        return ArtifactPreview(
            id=artifact_id,
            kind="html_preview",
            title=site_name,
            html=html,
            css=css,
            files={"index.html": f"<style>{css}</style>\n{html}", "styles.css": css},
            receipt=receipt,
        )

    def _infer_site_name(self, title: str, prompt: str) -> str:
        prompt_text = prompt.strip()
        match = re.search(r"\bfor\s+(.+?)(?:\s+using\b|\s+with\b|\s+in\b|$)", prompt_text, flags=re.IGNORECASE)
        if match:
            candidate = re.sub(r"\s+", " ", match.group(1)).strip(" .")
            if candidate:
                return candidate[:80]
        return title.strip() or "Inline website preview"

    def _infer_palette(self, prompt: str) -> dict[str, str]:
        lower = prompt.lower()
        if "red" in lower and "yellow" in lower:
            return {"background": "#1b0909", "surface": "#2a1010", "primary": "#e11d24", "secondary": "#ffd21f", "text": "#fff7ed"}
        if "blue" in lower:
            return {"background": "#061122", "surface": "#0d1b35", "primary": "#38bdf8", "secondary": "#93c5fd", "text": "#eff6ff"}
        return {"background": "#0b1020", "surface": "#111827", "primary": "#22d3ee", "secondary": "#f59e0b", "text": "#f8fafc"}

    def _build_css(self, palette: dict[str, str]) -> str:
        return f"""
html,body{{margin:0;min-height:100%;font-family:Inter,system-ui,Segoe UI,sans-serif;background:{palette['background']};color:{palette['text']};}}
.site-shell{{min-height:100vh;background:radial-gradient(circle at top left,{palette['primary']}44,transparent 34%),linear-gradient(135deg,{palette['background']},{palette['surface']});}}
.topbar{{display:flex;justify-content:space-between;gap:24px;padding:22px 44px;border-bottom:1px solid rgba(255,255,255,.14);background:rgba(0,0,0,.22);}}
.topbar strong{{color:{palette['secondary']};font-size:1.1rem;letter-spacing:.03em;}}
.topbar span{{opacity:.82;}}
.hero{{padding:72px 44px 56px;max-width:980px;}}
.eyebrow{{color:{palette['secondary']};font-weight:900;text-transform:uppercase;letter-spacing:.14em;}}
h1{{margin:.15em 0;font-size:clamp(2.7rem,8vw,5.8rem);line-height:.92;}}
.lead{{max-width:780px;font-size:1.25rem;line-height:1.7;color:rgba(255,255,255,.86);}}
.hero-actions{{display:flex;flex-wrap:wrap;gap:14px;margin-top:28px;}}
.button{{border-radius:999px;padding:13px 19px;text-decoration:none;font-weight:900;}}
.primary{{background:{palette['secondary']};color:#1b1200;}}
.secondary{{border:1px solid rgba(255,255,255,.26);color:{palette['text']};}}
.feature-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;padding:0 44px 44px;}}
.feature-grid article,.contact{{border:1px solid rgba(255,255,255,.16);border-radius:22px;background:rgba(0,0,0,.28);padding:24px;box-shadow:0 20px 60px rgba(0,0,0,.22);}}
.feature-grid h2,.contact h2{{margin-top:0;color:{palette['secondary']};}}
.contact{{margin:0 44px 44px;}}
@media(max-width:760px){{.topbar,.feature-grid{{display:block}}.hero,.topbar,.feature-grid,.contact{{padding-left:22px;padding-right:22px}}.feature-grid article{{margin-bottom:14px}}}}
""".strip()
