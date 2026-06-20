from x8.operator.contracts import OperatorRiskAssessment, RiskLevel


MUTATING = {"write_file", "apply_patch", "create_file", "git_commit", "run_test_preset", "run_docker_preset"}
DESTRUCTIVE = {"delete_file", "docker_rebuild", "install_package"}
EXTERNAL = {"git_push", "send_email", "send_sms", "calendar_create", "calendar_update"}
REMOTE = {"browser_click", "browser_type", "desktop_click", "desktop_type", "screenshot"}
READ_ONLY = {"open_file", "read_file", "git_status", "git_diff", "file_metadata", "directory_listing", "docker_status", "docker_logs"}
BLOCKED = {"arbitrary_shell"}


class RiskAssessor:
    def assess(self, action_type: str) -> OperatorRiskAssessment:
        if action_type in BLOCKED:
            return OperatorRiskAssessment(action_type=action_type, risk_level=RiskLevel.SYSTEM_LEVEL, requires_approval=True, reason="Arbitrary shell is blocked by the V8 Operator contract.")
        if action_type in READ_ONLY:
            return OperatorRiskAssessment(action_type=action_type, risk_level=RiskLevel.READ_ONLY, requires_approval=False, reason="Read-only observation.")
        if action_type in DESTRUCTIVE:
            return OperatorRiskAssessment(action_type=action_type, risk_level=RiskLevel.DESTRUCTIVE, requires_approval=True, reason="Destructive/system action requires stronger popup approval.")
        if action_type in EXTERNAL:
            return OperatorRiskAssessment(action_type=action_type, risk_level=RiskLevel.EXTERNAL_SEND, requires_approval=True, reason="External send requires target preview and popup approval.")
        if action_type in REMOTE:
            return OperatorRiskAssessment(action_type=action_type, risk_level=RiskLevel.REMOTE_CONTROL, requires_approval=True, reason="Remote control requires visible observation and popup approval.")
        if action_type in MUTATING:
            return OperatorRiskAssessment(action_type=action_type, risk_level=RiskLevel.NORMAL_MUTATION, requires_approval=True, reason="Mutation requires popup approval.")
        return OperatorRiskAssessment(action_type=action_type, risk_level=RiskLevel.LOW_MUTATION, requires_approval=True, reason="Unknown action defaults to approval-required.")
