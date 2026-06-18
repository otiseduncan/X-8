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
    summary = "GitHub integration contract exists; live operations require credentials and approval."
    status = CapabilityStatus.STUBBED


class BrowserAdapter(DisabledIntegrationAdapter):
    name = "browser"
    summary = "Live browser control is stubbed for future E2E and remote-control flows."
    status = CapabilityStatus.STUBBED


class RemoteAccessAdapter(DisabledIntegrationAdapter):
    name = "remote_access"
    summary = "Remote access is disabled by default and requires explicit approval policy."


class LocalBridgeAdapter(DisabledIntegrationAdapter):
    name = "local_bridge"
    summary = "Local bridge is disabled until explicitly configured."


class FileSystemAdapter(DisabledIntegrationAdapter):
    name = "filesystem"
    summary = "Filesystem mutation requires workspace scope and approval."
    status = CapabilityStatus.STUBBED


class ShellCommandAdapter(DisabledIntegrationAdapter):
    name = "shell_command"
    summary = "Shell mutation requires approval; read-only inspection may be added later."
    status = CapabilityStatus.STUBBED


class DockerAdapter(DisabledIntegrationAdapter):
    name = "docker"
    summary = "Docker mutation requires explicit approval."
    status = CapabilityStatus.STUBBED


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
        NotificationAdapter(),
    ]
