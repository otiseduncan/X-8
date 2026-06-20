from x8.contracts.capability import CapabilityStatus
from x8.contracts.integrations import IntegrationStatus


class DisabledIntegrationAdapter:
    name = "integration"
    summary = "Future integration contract exists but is not active."
    reason = "Integration is disabled by policy."
    credential_required = True
    approval_required = True
    status = CapabilityStatus.DISABLED
    live = False
    required_config: list[str] = []
    safe_actions: list[str] = ["read_status"]
    blocked_actions: list[str] = ["execute_write", "external_send"]

    def integration_status(self) -> IntegrationStatus:
        return IntegrationStatus(
            name=self.name,
            status=self.status,
            live=self.live,
            reason=self.reason,
            required_config=self.required_config,
            safe_actions=self.safe_actions,
            blocked_actions=self.blocked_actions,
            summary=self.summary,
            credential_required=self.credential_required,
            approval_required=self.approval_required,
            receipt={
                "action": "integration.status",
                "status": self.status,
                "live": self.live,
                "source": "integration_catalog",
            },
        )
