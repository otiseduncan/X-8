# Future Integrations

XV8 includes adapter contracts for future integrations while staying honest about current status.

## Adapters

- EmailAdapter
- SmsAdapter
- CalendarAdapter
- ContactsAdapter
- GitHubAdapter
- BrowserAdapter
- RemoteAccessAdapter
- LocalBridgeAdapter
- FileSystemAdapter
- ShellCommandAdapter
- DockerAdapter
- NotificationAdapter

GitHub, workspace inspection, file viewing, diff viewing, patch proposal, Docker preset visibility, and the in-screen development cockpit are MVP capabilities. GitHub is live when environment credentials are present and reports `not_configured` when they are absent.

Default status for destructive or external-write integrations remains disabled or stubbed unless credentials, runtime wiring, and approval gates exist.

No adapter may assume credentials or claim live access without proof.
