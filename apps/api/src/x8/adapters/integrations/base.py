from x8.contracts.capability import CapabilityStatus
from x8.contracts.integrations import IntegrationStatus


class DisabledIntegrationAdapter:
    name = "integration"
    summary = "Future integration contract exists but is not active."
    credential_required = True
    approval_required = True
    status = CapabilityStatus.DISABLED

    def integration_status(self) -> IntegrationStatus:
        return IntegrationStatus(
            name=self.name,
            status=self.status,
            summary=self.summary,
            credential_required=self.credential_required,
            approval_required=self.approval_required,
        )
