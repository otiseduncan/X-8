from x8.operator.contracts import OperatorCapability, RiskLevel, ToolSpec


class OperatorCapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, OperatorCapability] = {}
        self._tools: dict[str, ToolSpec] = {}

    def register(self, capability: OperatorCapability, tools: list[ToolSpec]) -> None:
        self._capabilities[capability.capability_id] = capability
        for tool in tools:
            self._tools[tool.action_type] = tool

    def capabilities(self) -> list[OperatorCapability]:
        return list(self._capabilities.values())

    def tool(self, action_type: str) -> ToolSpec | None:
        return self._tools.get(action_type)


def default_operator_registry() -> OperatorCapabilityRegistry:
    registry = OperatorCapabilityRegistry()
    registry.register(
        OperatorCapability(
            capability_id="operator.workspace_read",
            display_name="Workspace read-only tools",
            category="workspace",
            risk_level=RiskLevel.READ_ONLY,
            status="ready",
            manager="OperatorRuntime",
            adapter="LocalBridgeOperatorAdapter",
            supported_actions=["read_file", "open_file", "directory_listing", "file_metadata"],
        ),
        [
            ToolSpec(action_type="read_file", risk_level=RiskLevel.READ_ONLY, requires_approval=False, allowed_targets=["approved_roots"]),
            ToolSpec(action_type="file_metadata", risk_level=RiskLevel.READ_ONLY, requires_approval=False, allowed_targets=["approved_roots"]),
        ],
    )
    registry.register(
        OperatorCapability(
            capability_id="operator.mock_mutation",
            display_name="Mock mutation planner",
            category="safety",
            risk_level=RiskLevel.NORMAL_MUTATION,
            status="mock_only",
            manager="OperatorRuntime",
            adapter="MockOperatorExecutor",
            supported_actions=["write_file", "apply_patch", "delete_file"],
            requires_approval=True,
        ),
        [
            ToolSpec(action_type="write_file", risk_level=RiskLevel.NORMAL_MUTATION, requires_approval=True, supports_rollback=True, allowed_targets=["approved_roots"]),
            ToolSpec(action_type="delete_file", risk_level=RiskLevel.DESTRUCTIVE, requires_approval=True, supports_rollback=False, allowed_targets=["approved_roots"]),
        ],
    )
    return registry
