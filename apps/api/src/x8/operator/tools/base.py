from x8.operator.contracts import ToolInvocation, ToolResult, ToolSpec


class OperatorTool:
    spec: ToolSpec

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        return ToolResult(invocation_id=invocation.id, status="mock_only", output_summary="Tool scaffold only; no real action executed.")
