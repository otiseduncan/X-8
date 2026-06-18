# Manager Map

## Implemented Managers

- `AssistantManager`: coordinates chat responses and receipts.
- `TeamCouncilManager`: loads senior team seats and produces role-aware planning notes.
- `KnowledgeSeedManager`: reads seeded design, AI, DevOps, security, and product knowledge.
- `MemoryManager`: separates remembered facts from knowledge and verified status.
- `ArtifactManager`: creates preview artifacts without repo mutation.
- `UiDesignManager`: exposes practical UI design review guidance.
- `AiDesignManager`: exposes practical AI system design guidance.
- `OperatorManager`: models safe development workflow steps.
- `ApprovalManager`: blocks risky actions without explicit approval.
- `AuditManager`: records receipts in memory for the current runtime.
- `WorkspaceManager`: lists, searches, and reads files inside the approved workspace root.
- `SafeRepoWriterManager`: creates diffs and applies approved file updates inside the repo only.
- `DockerCommandPresetManager`: exposes Docker-only command presets and honest command receipts.

## Initial Safe Development Loop

`inspect -> plan -> propose patch -> approval required -> apply patch -> test -> receipt`

## MVP Cockpit

XV8 includes a browser-based project cockpit with file tree, search, file viewer, code editor surface, diff viewer, approval panel, Docker preset panel, logs panel, artifact/site preview, receipts, capability truth, and team seats.
