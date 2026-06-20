from x8.kernel.contracts import SafetyDecision


class SafetyGate:
    MUTATING_LANES = {"approval_required_action", "operator_blocked", "github_create_repo", "github_connect_init", "github_push", "github_pull", "self_build", "project_builder"}

    def decide(self, lane: str) -> SafetyDecision:
        if lane in self.MUTATING_LANES:
            return SafetyDecision(allowed=False, requires_approval=True, risk_level="mutating", reason="Mutating actions require click approval.")
        return SafetyDecision(allowed=True, requires_approval=False, risk_level="read_only")
