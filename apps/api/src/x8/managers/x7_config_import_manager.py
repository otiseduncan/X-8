import os
import re
from pathlib import Path

import yaml

from x8.contracts.imports import ImportedConfigValue, LegacyConfigImportReport, LegacySourceStatus, X7ImportReport

ALLOWED_NAMES = {".env", ".env.local", ".env.example", "docker-compose.yml", "compose.yaml"}
ALLOWED_SUFFIXES = {".env", ".json", ".yaml", ".yml"}
SECRET_MARKERS = ("TOKEN", "KEY", "SECRET", "PASSWORD")
IGNORED_DIRS = {".git", "node_modules", "dist", "build", "coverage", "__pycache__", ".pytest_cache", "runtime", "logs", ".venv", "venv", "env", "site-packages"}
MAX_CONFIG_BYTES = 500_000


class SingleSourceConfigImportManager:
    name = "single_source_config_import"
    version = "0.1.0"

    def __init__(self, import_root: str, map_path: str = "/workspace/config/migration/x6_x7_to_xv8_env_map.yaml") -> None:
        self.import_root = Path(import_root).resolve()
        self.map_path = Path(map_path)

    def _allowed(self, path: Path) -> bool:
        rel = path.relative_to(self.import_root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            return False
        if rel.name in ALLOWED_NAMES or rel.suffix in ALLOWED_SUFFIXES:
            return True
        return len(rel.parts) == 2 and rel.parts[0] == "config" and rel.suffix in {".yml", ".yaml", ".json"}

    def _mapping(self) -> dict[str, str]:
        if not self.map_path.exists():
            return {}
        return yaml.safe_load(self.map_path.read_text(encoding="utf-8")) or {}

    def files(self, limit: int = 250) -> list[Path]:
        if not self.import_root.exists():
            return []
        found: list[Path] = []
        for root, dirs, files in os.walk(self.import_root):
            dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
            root_path = Path(root)
            for name in files:
                path = root_path / name
                if self._allowed(path) and path.stat().st_size <= MAX_CONFIG_BYTES:
                    found.append(path)
                    if len(found) >= limit:
                        return found
        return found

    def classify(self, name: str, value: str) -> str:
        upper = name.upper()
        if any(marker in upper for marker in SECRET_MARKERS):
            return "api_key" if "KEY" in upper else "token"
        if "URL" in upper or value.startswith(("http://", "https://")):
            return "url"
        if "USER" in upper:
            return "username"
        return "safe_default" if value and len(value) < 40 else "unknown"

    def provider_for(self, name: str) -> str:
        upper = name.upper()
        if "BRAVE" in upper:
            return "brave_search"
        if "SERPAPI" in upper:
            return "serpapi"
        if "TAVILY" in upper:
            return "tavily"
        if "BING" in upper:
            return "bing_search"
        if "SEARXNG" in upper:
            return "SearXNG"
        if "COMFY" in upper:
            return "ComfyUI"
        if "GITHUB" in upper or upper.startswith("GH_"):
            return "github"
        if "OLLAMA" in upper:
            return "ollama"
        if "BRIDGE" in upper:
            return "local_bridge"
        return "unknown"

    def redact(self, value: str, classification: str) -> str:
        if classification in {"secret", "token", "api_key", "password"}:
            return f"{value[:3]}...{value[-3:]}" if len(value) >= 7 else "***"
        return value

    def parse_values(self, text: str) -> dict[str, str]:
        found: dict[str, str] = {}
        for match in re.finditer(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*[\"']?([^\"'\n#]+)", text):
            found[match.group(1)] = match.group(2).strip()
        return found

    def scan(self) -> X7ImportReport:
        mapping = self._mapping()
        values: list[ImportedConfigValue] = []
        for path in self.files():
            parsed = self.parse_values(path.read_text(encoding="utf-8", errors="ignore"))
            for name, value in parsed.items():
                recommended = mapping.get(name)
                if not recommended:
                    continue
                classification = self.classify(name, value)
                values.append(
                    ImportedConfigValue(
                        name=name,
                        detected_provider=self.provider_for(name),
                        value_present=bool(value),
                        redacted_preview=self.redact(value, classification),
                        recommended_xv8_env_name=recommended,
                        classification=classification,
                    )
                )
        providers = sorted({item.detected_provider for item in values if item.detected_provider != "unknown"})
        present = {item.recommended_xv8_env_name for item in values}
        missing = sorted(set(mapping.values()) - present)
        template = "\n".join(f"{item.recommended_xv8_env_name}=" for item in values)
        return X7ImportReport(
            import_root=str(self.import_root),
            files_discovered=[str(path.relative_to(self.import_root)) for path in self.files()],
            providers_discovered=providers,
            values=values,
            missing_recommended_variables=missing,
            env_local_template=template,
        )

    def write_runtime_reports(self) -> X7ImportReport:
        report = self.scan()
        out_dir = Path("/workspace/runtime/import-reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        return report


class LegacyConfigImportManager:
    name = "legacy_config_import"
    version = "0.1.0"

    def __init__(
        self,
        x7_import_root: str,
        x6_import_root: str,
        map_path: str = "/workspace/config/migration/x6_x7_to_xv8_env_map.yaml",
    ) -> None:
        self.x7 = SingleSourceConfigImportManager(x7_import_root, map_path)
        self.x6 = SingleSourceConfigImportManager(x6_import_root, map_path)

    def scan(self) -> LegacyConfigImportReport:
        x7_report = self.x7.scan()
        x6_report = self.x6.scan()
        x7_providers = sorted(set(x7_report.providers_discovered + self._file_provider_hints(x7_report)))
        x6_providers = sorted(set(x6_report.providers_discovered + self._file_provider_hints(x6_report)))
        x7_status = self._source_status("x7", "X:\\XV7\\xv7", "/imports/x7", self.x7, x7_report, x7_providers)
        x6_status = self._source_status("x6", "X:\\X-V-6.1", "/imports/x6", self.x6, x6_report, x6_providers)
        providers = sorted(set(x7_providers + x6_providers))
        secrets = [
            value
            for value in x7_report.values + x6_report.values
            if value.classification in {"secret", "token", "api_key", "password"}
        ]
        missing_paths = x7_status.missing_paths + x6_status.missing_paths
        recommendations = self._recommendations(x7_report, x6_report)
        return LegacyConfigImportReport(
            x7_import_status=x7_status,
            x6_import_status=x6_status,
            x7_files_found=len(x7_report.files_discovered),
            x6_files_found=len(x6_report.files_discovered),
            x7_configs_found=len(x7_report.files_discovered),
            x6_configs_found=len(x6_report.files_discovered),
            providers_found=providers,
            secrets_detected_redacted=secrets,
            missing_paths=missing_paths,
            migration_recommendations=recommendations,
            x7_report=x7_report,
            x6_report=x6_report,
        )

    def write_runtime_reports(self) -> LegacyConfigImportReport:
        report = self.scan()
        out_dir = Path("/workspace/runtime/import-reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "x7-config-import-redacted.json").write_text(report.x7_report.model_dump_json(indent=2), encoding="utf-8")
        (out_dir / "x6-config-import-redacted.json").write_text(report.x6_report.model_dump_json(indent=2), encoding="utf-8")
        summary = (
            "# Legacy Config Import Summary\n\n"
            f"X7 files found: {report.x7_files_found}\n"
            f"X6 files found: {report.x6_files_found}\n"
            f"Providers: {', '.join(report.providers_found) or 'none'}\n"
            f"Redacted secrets detected: {len(report.secrets_detected_redacted)}\n"
        )
        (out_dir / "legacy-config-import-summary.md").write_text(summary, encoding="utf-8")
        return report

    def _source_status(
        self,
        source_id: str,
        source_path: str,
        mount_path: str,
        manager: SingleSourceConfigImportManager,
        report: X7ImportReport,
        providers: list[str],
    ) -> LegacySourceStatus:
        exists = manager.import_root.exists()
        return LegacySourceStatus(
            source_id=source_id,
            source_path=source_path,
            mount_path=mount_path,
            import_status="available" if exists else "missing_path",
            files_found=len(report.files_discovered),
            configs_found=len(report.files_discovered),
            providers_found=providers,
            missing_paths=[] if exists else [mount_path],
        )

    def _file_provider_hints(self, report: X7ImportReport) -> list[str]:
        providers: set[str] = set()
        for rel_path in report.files_discovered:
            lower = rel_path.lower()
            if "searxng" in lower or "search" in lower:
                providers.add("SearXNG")
            if "comfyui" in lower or "image-workflow" in lower or "workflow" in lower:
                providers.add("ComfyUI")
            if "github" in lower:
                providers.add("github")
            if "avatar" in lower:
                providers.add("avatar")
            if "speech" in lower or "tts" in lower or "voice" in lower:
                providers.add("speech")
        return sorted(providers)

    def _recommendations(self, x7_report: X7ImportReport, x6_report: X7ImportReport) -> list[str]:
        recommendations: list[str] = []
        if any(value.detected_provider == "github" for value in x7_report.values):
            recommendations.append("Use X7 GitHub values for XV8 GitHub runtime env.")
        if any(value.detected_provider == "ComfyUI" for value in x6_report.values):
            recommendations.append("Use X6 ComfyUI values for XV8 image-generation env.")
        if any(value.detected_provider in {"SearXNG", "brave_search", "serpapi", "tavily", "bing_search"} for value in x6_report.values):
            recommendations.append("Use X6 search values for XV8 web-search env.")
        return recommendations


class X7ConfigImportManager(SingleSourceConfigImportManager):
    name = "x7_config_import"

    def __init__(self, import_root: str, map_path: str = "/workspace/config/migration/x6_x7_to_xv8_env_map.yaml") -> None:
        super().__init__(import_root, map_path)
