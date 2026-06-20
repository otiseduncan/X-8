from x8.adapters.integrations.base import DisabledIntegrationAdapter
from x8.contracts.capability import CapabilityStatus


class EmailAdapter(DisabledIntegrationAdapter):
    name = "email"
    summary = "Email sending is disabled until credentials and approval gates are configured."


class SmsAdapter(DisabledIntegrationAdapter):
    name = "sms"
    summary = "SMS sending is disabled until provider credentials and approval gates are configured."


class CalendarAdapter(DisabledIntegrationAdapter):
    name = "calendar"
    summary = "Calendar access is stubbed and performs no reads or writes."
    status = CapabilityStatus.STUBBED


class ContactsAdapter(DisabledIntegrationAdapter):
    name = "contacts"
    summary = "Contacts access is stubbed and performs no reads or writes."
    status = CapabilityStatus.STUBBED


class GitHubAdapter(DisabledIntegrationAdapter):
    name = "github"
    summary = "GitHub Ops routes are implemented; writes require approval and credentials."
    reason = "Repository inspection is available locally; remote writes are approval-gated and token-dependent."
    status = CapabilityStatus.IMPLEMENTED
    credential_required = True
    safe_actions = ["read_local_status", "preview_pull", "preview_push", "prepare_create_repo"]
    blocked_actions = ["commit_without_approval", "push_without_approval", "create_repo_without_approval"]


class BrowserAdapter(DisabledIntegrationAdapter):
    name = "browser"
    summary = "Browser UI is served by the web app; remote browser control is not enabled."
    reason = "The cockpit UI can run in a browser, but broad browser automation is not wired into chat."
    status = CapabilityStatus.IMPLEMENTED
    safe_actions = ["open_ui", "run_e2e_tests"]
    blocked_actions = ["remote_browser_control_from_chat"]


class RemoteAccessAdapter(DisabledIntegrationAdapter):
    name = "remote_access"
    summary = "Remote access is disabled by default and requires explicit approval policy."


class LocalBridgeAdapter(DisabledIntegrationAdapter):
    name = "local_bridge"
    summary = "Local bridge service is declared in compose and only exposes bounded read-only helper status."
    reason = "Bridge availability must be checked through /api/local-bridge/status; no chat shell bridge is enabled."
    status = CapabilityStatus.IMPLEMENTED
    credential_required = False
    safe_actions = ["read_status"]
    blocked_actions = ["arbitrary_host_control", "shell_from_chat"]


class FileSystemAdapter(DisabledIntegrationAdapter):
    name = "filesystem"
    summary = "Workspace reads and approval-gated writes are implemented for approved paths."
    reason = "Runtime writes are blocked unless approval-gated or inside the configured project-builder sandbox."
    status = CapabilityStatus.IMPLEMENTED
    credential_required = False
    safe_actions = ["read_workspace", "preview_patch", "write_approved_sandbox_project"]
    blocked_actions = ["write_without_approval", "write_outside_sandbox", "read_secrets"]


class ShellCommandAdapter(DisabledIntegrationAdapter):
    name = "shell_command"
    summary = "Arbitrary shell from chat is blocked; only allowlisted validation presets exist."
    reason = "Release policy blocks broad shell execution from user chat."
    status = CapabilityStatus.BLOCKED
    safe_actions = ["run_allowlisted_validation_preset"]
    blocked_actions = ["arbitrary_shell", "destructive_shell", "commit_or_push_from_chat"]


class DockerAdapter(DisabledIntegrationAdapter):
    name = "docker"
    summary = "Docker compose validation is the supported runtime path."
    reason = "Docker is required externally; live daemon state is proven by docker compose commands, not assumed."
    status = CapabilityStatus.IMPLEMENTED
    credential_required = False
    safe_actions = ["compose_config", "compose_build", "run_test_services"]
    blocked_actions = ["destructive_container_mutation_from_chat"]


class OllamaAdapter(DisabledIntegrationAdapter):
    name = "ollama"
    summary = "Ollama model status is checked through the configured base URL."
    reason = "Models are live only when the status endpoint proves reachability and selected model readiness."
    status = CapabilityStatus.IMPLEMENTED
    credential_required = False
    required_config = ["X8_OLLAMA_BASE_URL", "X8_DEFAULT_CHAT_MODEL"]
    safe_actions = ["read_model_status", "generate_chat_when_ready"]
    blocked_actions = ["claim_model_live_without_probe"]


class SearXNGAdapter(DisabledIntegrationAdapter):
    name = "searxng"
    summary = "SearXNG search is optional and reports unavailable when the service is not reachable."
    reason = "The search route must not claim live web search unless the configured provider responds."
    status = CapabilityStatus.NOT_CONFIGURED
    credential_required = False
    required_config = ["search profile or reachable X8_SEARXNG_BASE_URL"]
    safe_actions = ["read_search_status"]
    blocked_actions = ["fake_web_results"]


class ComfyUIAdapter(DisabledIntegrationAdapter):
    name = "comfyui"
    summary = "ComfyUI image generation is optional and approval-gated."
    reason = "Image generation is live only when the ComfyUI service and model directory are reachable."
    status = CapabilityStatus.NOT_CONFIGURED
    credential_required = False
    required_config = ["image profile or reachable X8_COMFYUI_BASE_URL", "model checkpoints"]
    safe_actions = ["read_image_status", "prepare_image_request"]
    blocked_actions = ["claim_generated_image_without_artifact", "unsafe_external_model_fetch"]


class SpeechAdapter(DisabledIntegrationAdapter):
    name = "speech_tts"
    summary = "Browser speech preferences are implemented; cloud TTS is unavailable without credentials."
    reason = "The UI can use browser speech synthesis; Google TTS requires credentials before server-side speech is live."
    status = CapabilityStatus.IMPLEMENTED
    required_config = ["GOOGLE_TTS_API_KEY or browser speech synthesis"]
    safe_actions = ["read_speech_status", "browser_read_aloud"]
    blocked_actions = ["claim_cloud_tts_without_credentials"]


class MemoryAdapter(DisabledIntegrationAdapter):
    name = "memory_database"
    summary = "Brain memory uses the configured database and redaction/approval policy."
    reason = "Memory CRUD and retrieval are implemented; secret-like content remains blocked."
    status = CapabilityStatus.IMPLEMENTED
    credential_required = False
    safe_actions = ["remember_low_risk", "retrieve_active", "approve_pending", "forget_soft_delete"]
    blocked_actions = ["save_secret", "use_pending_memory", "dump_raw_database"]


class SelfBuildAdapter(DisabledIntegrationAdapter):
    name = "self_build_operator"
    summary = "Self-build proposals and approved patch apply are implemented with hash approval."
    reason = "Patch writes require approval id, patch id, exact patch hash, and unchanged before hashes."
    status = CapabilityStatus.IMPLEMENTED
    credential_required = False
    safe_actions = ["create_patch_proposal", "apply_approved_patch", "run_allowlisted_validation"]
    blocked_actions = ["silent_self_modification", "auto_commit", "auto_push"]


class NotificationAdapter(DisabledIntegrationAdapter):
    name = "notification"
    summary = "Notifications are stubbed and do not send messages."
    status = CapabilityStatus.STUBBED


def integration_catalog() -> list[DisabledIntegrationAdapter]:
    return [
        EmailAdapter(),
        SmsAdapter(),
        CalendarAdapter(),
        ContactsAdapter(),
        GitHubAdapter(),
        BrowserAdapter(),
        RemoteAccessAdapter(),
        LocalBridgeAdapter(),
        FileSystemAdapter(),
        ShellCommandAdapter(),
        DockerAdapter(),
        OllamaAdapter(),
        SearXNGAdapter(),
        ComfyUIAdapter(),
        SpeechAdapter(),
        MemoryAdapter(),
        SelfBuildAdapter(),
        NotificationAdapter(),
    ]
