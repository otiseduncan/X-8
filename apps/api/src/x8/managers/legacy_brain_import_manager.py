import json
from pathlib import Path
from typing import Any


class LegacyBrainImportManager:
    KEYWORDS = ("brain", "memory", "knowledge", "preference", "prompt", "persona", "context", "receipt", "model")

    def __init__(self, x7_root: str, x6_root: str, report_root: str = "/workspace/runtime/import-reports") -> None:
        self.roots = {"x7": Path(x7_root), "x6": Path(x6_root)}
        self.report_root = Path(report_root)

    def scan(self) -> dict[str, Any]:
        report = {"sources": {}, "records": [], "limitations": []}
        for label, root in self.roots.items():
            files = self._scan_root(root)
            report["sources"][label] = {"path": str(root), "available": root.exists(), "files_found": len(files)}
            report["records"].extend({"source": label, **item} for item in files[:100])
            if not root.exists():
                report["limitations"].append(f"{label} import path unavailable: {root}")
        self._write_reports(report)
        return report

    def scan_memory_candidates(self) -> dict[str, Any]:
        report = {"sources": {}, "memory_candidates": [], "limitations": []}
        seen: set[str] = set()
        for label, root in self.roots.items():
            files = self._scan_root(root)
            report["sources"][label] = {"path": str(root), "available": root.exists(), "files_found": len(files)}
            if not root.exists():
                report["limitations"].append(f"{label} import path unavailable: {root}")
            for item in files:
                preview = str(item["preview"])
                dedupe_key = preview[:200].strip().lower()
                if not dedupe_key or dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                report["memory_candidates"].append(
                    {
                        "status": "pending",
                        "source": f"legacy_import_{label}",
                        "source_path": item["path"],
                        "memory_type": self._classify_memory_type(item["path"], preview),
                        "confidence": 0.45,
                        "preview": preview,
                    }
                )
        self._write_memory_reports(report)
        return report

    def _scan_root(self, root: Path) -> list[dict[str, Any]]:
        if not root.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".txt", ".yaml", ".yml"}:
                continue
            haystack = f"{path.name} {'/'.join(path.parts)}".lower()
            if not any(keyword in haystack for keyword in self.KEYWORDS):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if self._looks_secret(text):
                preview = "[redacted secret-like file]"
            else:
                preview = text[:500]
            records.append({"path": str(path), "kind": path.suffix.lower().lstrip("."), "preview": preview})
        return records

    def _looks_secret(self, text: str) -> bool:
        lower = text.lower()
        return any(term in lower for term in ("api_key", "api key", "token=", "token:", "password", "secret", "private_key", "private key", "service_account"))

    def _write_reports(self, report: dict[str, Any]) -> None:
        self.report_root.mkdir(parents=True, exist_ok=True)
        (self.report_root / "legacy-brain-import-redacted.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines = ["# Legacy Brain Import Summary", ""]
        for label, source in report["sources"].items():
            lines.append(f"- {label}: {source['files_found']} candidate files; available={source['available']}")
        lines.append("")
        lines.append("Secrets are redacted. Runtime logs are not promoted to tracked knowledge.")
        (self.report_root / "legacy-brain-import-summary.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_memory_reports(self, report: dict[str, Any]) -> None:
        self.report_root.mkdir(parents=True, exist_ok=True)
        (self.report_root / "legacy-memory-import-redacted.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines = ["# Legacy Memory Import Summary", ""]
        for label, source in report["sources"].items():
            lines.append(f"- {label}: {source['files_found']} candidate source files; available={source['available']}")
        lines.append(f"- pending memory candidates: {len(report['memory_candidates'])}")
        lines.append("")
        lines.append("Candidates are pending only. Secrets are redacted. No legacy memory is auto-activated.")
        (self.report_root / "legacy-memory-import-summary.md").write_text("\n".join(lines), encoding="utf-8")

    def _classify_memory_type(self, path: str, preview: str) -> str:
        text = f"{path} {preview}".lower()
        if "voice" in text or "avatar" in text:
            return "voice_avatar_preference"
        if "model" in text or "ollama" in text:
            return "model_configuration"
        if "tool" in text or "github" in text or "comfyui" in text or "searx" in text:
            return "tool_configuration"
        if "design" in text or "ui" in text:
            return "design_preference"
        if "preference" in text or "prefer" in text:
            return "user_preference"
        if "status" in text or "verified" in text:
            return "verified_status_pointer"
        if "workflow" in text or "habit" in text:
            return "workflow_preference"
        return "project_fact"
