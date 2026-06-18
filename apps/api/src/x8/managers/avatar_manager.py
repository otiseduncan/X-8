import json
import shutil
from pathlib import Path

from x8.contracts.avatar import AvatarAsset, AvatarImportReceipt, AvatarManifest, AvatarState, AvatarStatus

AVATAR_EXTENSIONS = {".glb", ".gltf", ".vrm", ".fbx", ".obj", ".usdz", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".json", ".anim", ".bin", ".mp4", ".webm", ".mov", ".m4v"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
LIKELY_PARTS = {"shared", "assets", "avatar", "avatars", "public", "generated-assets"}


class AvatarAssetImportManager:
    name = "avatar_asset_import"
    version = "0.1.0"

    def __init__(self, import_root: str, output_root: str = "/workspace/apps/web/public/avatar") -> None:
        self.import_root = Path(import_root).resolve()
        self.output_root = Path(output_root)

    def scan(self) -> list[Path]:
        if not self.import_root.exists():
            return []
        found: list[Path] = []
        for path in self.import_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in AVATAR_EXTENSIONS:
                continue
            rel_parts = {part.lower() for part in path.relative_to(self.import_root).parts}
            if "log" in rel_parts or "logs" in rel_parts:
                continue
            if rel_parts & LIKELY_PARTS or "avatar" in path.name.lower():
                found.append(path)
        return found[:50]

    def import_assets(self) -> tuple[AvatarManifest, AvatarImportReceipt]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        imported: list[AvatarAsset] = []
        for source in self.scan():
            if source.stat().st_size > 5_000_000:
                continue
            target = self.output_root / source.name
            shutil.copy2(source, target)
            imported.append(AvatarAsset(path=f"/avatar/{target.name}", asset_type=target.suffix.lower().lstrip("."), imported=True))
        manifest = AvatarManager(str(self.output_root)).manifest(imported)
        (self.output_root / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        report_dir = Path("/workspace/runtime/import-reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "avatar-import-summary.md").write_text(f"# Avatar Import Summary\n\nAssets imported: {len(imported)}\n", encoding="utf-8")
        return manifest, AvatarImportReceipt(status=manifest.status, assets_imported=len(imported))


class AvatarManager:
    name = "avatar"
    version = "0.1.0"

    def __init__(self, avatar_root: str = "/workspace/apps/web/public/avatar") -> None:
        self.avatar_root = Path(avatar_root)

    def manifest(self, imported_assets: list[AvatarAsset] | None = None) -> AvatarManifest:
        fallback = self.avatar_root / "fallback.svg"
        existing = imported_assets if imported_assets is not None else self._assets()
        if existing:
            return AvatarManifest(status="ready", reason="Avatar assets are available.", fallback_available=fallback.exists(), default_asset=existing[0].path, assets=existing)
        return AvatarManifest(status="degraded_fallback" if fallback.exists() else "missing_assets", reason="No avatar assets found in approved X7 import path", fallback_available=fallback.exists(), default_asset="/avatar/fallback.svg" if fallback.exists() else None, assets=[])

    def state(self) -> AvatarState:
        manifest = self.manifest()
        return AvatarState(active_asset=manifest.default_asset, speech_state="idle")

    def status(self, active_state: str = "idle") -> AvatarStatus:
        manifest_path = self.avatar_root / "manifest.json"
        fallback = self.avatar_root / "fallback.svg"
        manifest_found = manifest_path.exists()
        limitations: list[str] = []
        assets = self._assets_from_manifest(manifest_path, limitations) if manifest_found else self._assets()
        states = sorted({state for asset in assets for state in asset.states})
        video_count = sum(1 for asset in assets if asset.asset_type == "video" or Path(asset.path).suffix.lower() in VIDEO_EXTENSIONS)
        status = "ready" if manifest_found and video_count >= 3 and not limitations else "degraded_fallback"
        if not manifest_found and not assets:
            status = "missing_assets"
        if limitations and not fallback.exists():
            status = "error"
        return AvatarStatus(
            status=status,
            manifest_found=manifest_found,
            asset_count=len(assets),
            video_asset_count=video_count,
            active_state=active_state,
            states_available=states,
            fallback_available=fallback.exists(),
            limitations=limitations,
        )

    def _assets_from_manifest(self, manifest_path: Path, limitations: list[str]) -> list[AvatarAsset]:
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            limitations.append(f"manifest.json could not be read: {exc}")
            return []
        assets: list[AvatarAsset] = []
        for item in data.get("assets", []):
            src = str(item.get("src", ""))
            asset_path = self.avatar_root / Path(src).name
            if not asset_path.exists():
                limitations.append(f"{src} is referenced but missing.")
            assets.append(
                AvatarAsset(
                    path=src,
                    asset_type=str(item.get("type", "video" if asset_path.suffix.lower() in VIDEO_EXTENSIONS else asset_path.suffix.lower().lstrip("."))),
                    imported=True,
                    id=str(item.get("id", "")),
                    label=str(item.get("label", "")),
                    states=[str(state) for state in item.get("states", [])],
                    loop=bool(item.get("loop", True)),
                    muted=bool(item.get("muted", True)),
                )
            )
        return assets

    def _assets(self) -> list[AvatarAsset]:
        if not self.avatar_root.exists():
            return []
        return [
            AvatarAsset(path=f"/avatar/{path.name}", asset_type="video" if path.suffix.lower() in VIDEO_EXTENSIONS else path.suffix.lower().lstrip("."), imported=path.name != "fallback.svg", id=path.stem)
            for path in self.avatar_root.iterdir()
            if path.is_file() and path.suffix.lower() in AVATAR_EXTENSIONS and path.name not in {"manifest.json", "fallback.svg"}
        ]
