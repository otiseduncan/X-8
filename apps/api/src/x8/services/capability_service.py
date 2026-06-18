from x8.contracts.capability import Capability, CapabilityStatus


def list_capabilities() -> list[Capability]:
    return [
        Capability(name="chat_receipts", status=CapabilityStatus.IMPLEMENTED, summary="Chat responses include receipts."),
        Capability(name="team_council", status=CapabilityStatus.IMPLEMENTED, summary="Seeded team seats are loaded."),
        Capability(name="artifact_preview", status=CapabilityStatus.IMPLEMENTED, summary="HTML preview artifacts can be created."),
        Capability(name="github_adapter", status=CapabilityStatus.IMPLEMENTED, summary="GitHub status and repo metadata adapter is available."),
        Capability(name="workspace_files", status=CapabilityStatus.IMPLEMENTED, summary="Workspace file tree, search, and read are available."),
        Capability(name="cockpit_ide", status=CapabilityStatus.IMPLEMENTED, summary="Browser-based development cockpit surfaces project work."),
        Capability(name="docker_presets", status=CapabilityStatus.IMPLEMENTED, summary="Docker command presets are exposed with receipts."),
        Capability(name="patch_proposal", status=CapabilityStatus.IMPLEMENTED, summary="Patch proposal creates visible diffs without writing."),
        Capability(name="SearXNG_web_search", status=CapabilityStatus.IMPLEMENTED, summary="SearXNG provider status and research receipts are available."),
        Capability(name="ComfyUI_image_generation", status=CapabilityStatus.IMPLEMENTED, summary="ComfyUI status and Juggernaut model detection are available."),
        Capability(name="x7_config_import", status=CapabilityStatus.IMPLEMENTED, summary="Approved X7 config import scans and redacts provider values."),
        Capability(name="local_bridge", status=CapabilityStatus.IMPLEMENTED, summary="Read-only local bridge service and status adapter are available."),
        Capability(name="avatar_surface", status=CapabilityStatus.IMPLEMENTED, summary="Avatar manifest, fallback asset, import path, and cockpit UI are available."),
        Capability(name="speech_output", status=CapabilityStatus.IMPLEMENTED, summary="Speech preferences default to US Google female with browser fallback status."),
        Capability(name="repo_write", status=CapabilityStatus.BLOCKED, summary="Repo writes require approval.", requires_approval=True),
        Capability(name="email_send", status=CapabilityStatus.DISABLED, summary="Email is not wired."),
        Capability(name="sms_send", status=CapabilityStatus.DISABLED, summary="SMS is not wired."),
        Capability(name="remote_access", status=CapabilityStatus.DISABLED, summary="Remote access is disabled by default."),
        Capability(name="browser_control", status=CapabilityStatus.STUBBED, summary="Browser control contract exists for future use."),
    ]
