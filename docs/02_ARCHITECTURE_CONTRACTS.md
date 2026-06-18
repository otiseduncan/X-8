# Architecture Contracts

XV8 managers and adapters communicate through structured contracts, not loose strings.

## Core Contracts

- `ResultEnvelope`
- `Receipt`
- `Evidence`
- `Capability`
- `CapabilityStatus`
- `ApprovalRequest`
- `RiskLevel`
- `PlanStep`
- `TeamSeat`
- `ManagerContext`
- `ManagerResponse`
- `ToolCallRequest`
- `ToolCallResult`
- `IntegrationStatus`

## Manager Protocol

Every manager exposes:

- `name`
- `version`
- `capabilities()`
- `plan(context)`
- `execute(context)`

Managers may inspect and propose. They may not mutate files, send messages, access remote systems, or run risky tools without approval.
