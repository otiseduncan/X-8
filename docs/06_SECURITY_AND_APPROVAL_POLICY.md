# Security And Approval Policy

XV8 defaults to safe, honest behavior.

## Approval Rules

- Tier 0 read-only inspection runs without approval.
- Tier 1 normal writes use an in-screen Approve / Cancel modal.
- Tier 2 destructive actions use a stronger modal and deliberate second click.
- Remote control is disabled by default.
- Email, SMS, calendar writes, and contact writes are disabled by default.
- Docker mutation, shell mutation, and filesystem mutation require approval.
- No credentials are stored in the repo.

## Remote Access Policy

- Read-only before control.
- Explicit user approval required.
- Click approval for high-risk actions by default.
- Session receipts and audit logs.
- No hidden access.
- No background control.
- No destructive host actions without a separate high-risk approval path.
