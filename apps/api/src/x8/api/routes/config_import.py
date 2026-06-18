from fastapi import APIRouter, Request

from x8.contracts.base import ResultEnvelope
from x8.contracts.imports import LegacyConfigImportReport, X7ImportReport
from x8.managers.x7_config_import_manager import LegacyConfigImportManager, X7ConfigImportManager

router = APIRouter(prefix="/api/config-import", tags=["config_import"])


def manager(request: Request) -> X7ConfigImportManager:
    return X7ConfigImportManager(request.app.state.settings.x7_import_root)


def legacy_manager(request: Request) -> LegacyConfigImportManager:
    settings = request.app.state.settings
    return LegacyConfigImportManager(settings.x7_import_root, settings.x6_import_root)


@router.get("/x7/status", response_model=ResultEnvelope[dict[str, object]])
def status(request: Request) -> ResultEnvelope[dict[str, object]]:
    root = request.app.state.settings.x7_import_root
    files = manager(request).files()
    return ResultEnvelope(ok=True, status="implemented", data={"import_root": root, "files_discovered": len(files)}, message="X7 import root inspected.")


@router.post("/x7/scan", response_model=ResultEnvelope[X7ImportReport])
def scan(request: Request) -> ResultEnvelope[X7ImportReport]:
    report = manager(request).scan()
    return ResultEnvelope(ok=True, status="completed", data=report, message="Redacted X7 config scan completed.")


@router.get("/legacy/status", response_model=ResultEnvelope[dict[str, object]])
def legacy_status(request: Request) -> ResultEnvelope[dict[str, object]]:
    report = legacy_manager(request).scan()
    settings = request.app.state.settings
    data = {
        "x7_source_path": "X:\\XV7\\xv7",
        "x7_mount_path": "/imports/x7",
        "x7_import_status": report.x7_import_status.import_status,
        "x7_files_found": report.x7_files_found,
        "x6_source_path": "X:\\X-V-6.1",
        "x6_mount_path": "/imports/x6",
        "x6_import_status": report.x6_import_status.import_status,
        "x6_files_found": report.x6_files_found,
        "github_config_found_in_x7": "github" in report.x7_import_status.providers_found,
        "comfyui_config_found_in_x6": "ComfyUI" in report.x6_import_status.providers_found,
        "search_config_found_in_x6": bool({"SearXNG", "brave_search", "serpapi", "tavily", "bing_search"} & set(report.x6_import_status.providers_found)),
        "avatar_assets_found": _avatar_assets_found(settings.x7_import_root) or _avatar_assets_found(settings.x6_import_root),
        "speech_config_found": any("SPEECH" in value.name or "TTS" in value.name or "VOICE" in value.name for value in report.x7_report.values + report.x6_report.values),
        "api_keys_detected_redacted": bool(report.secrets_detected_redacted),
    }
    return ResultEnvelope(ok=True, status="implemented", data=data, message="Legacy setup wizard status loaded.")


@router.post("/legacy/scan", response_model=ResultEnvelope[LegacyConfigImportReport])
def legacy_scan(request: Request) -> ResultEnvelope[LegacyConfigImportReport]:
    report = legacy_manager(request).write_runtime_reports()
    return ResultEnvelope(ok=True, status="completed", data=report, message="Redacted X6/X7 legacy config scan completed.")


def _avatar_assets_found(root: str) -> bool:
    from pathlib import Path
    import os

    ignored = {".git", "node_modules", "dist", "build", "coverage", "__pycache__", "runtime", "logs"}
    allowed = {".glb", ".gltf", ".vrm", ".fbx", ".obj", ".usdz", ".png", ".jpg", ".jpeg", ".webp", ".svg"}
    root_path = Path(root)
    if not root_path.exists():
        return False
    checked = 0
    for root_dir, dirs, files in os.walk(root_path):
        dirs[:] = [name for name in dirs if name not in ignored]
        for name in files:
            checked += 1
            if checked > 3000:
                return False
            path = Path(root_dir) / name
            if path.suffix.lower() in allowed and "avatar" in str(path).lower():
                return True
    return False
