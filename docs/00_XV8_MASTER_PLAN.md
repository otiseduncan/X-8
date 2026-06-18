# XV8 Master Plan

XV8 is a Docker-first AI assistant and development-team platform. It favors contract-first managers, honest capability status, preview-before-write workflows, and small files over central orchestration.

## Build Principles

- Docker is the only supported runtime surface.
- Every manager returns structured contracts and receipts.
- Future integrations are represented as disabled or stubbed adapters until configured.
- Repo mutation requires approval and produces an audit receipt.
- Knowledge, memory, verified status, and preferences remain separate concepts.
- Frontend artifact work defaults to preview and code view, not repo writes.

## Initial Runtime

- FastAPI backend under `apps/api`.
- React/Vite frontend under `apps/web`.
- PostgreSQL, Redis, and Ollama-ready services in Compose.
- Architecture guard runs through Docker and enforces file-size limits.
- Tests run through Docker services only.

## First Milestone

The first milestone is a working scaffold that exposes health, capabilities, integrations, team seed knowledge, chat receipts, artifact preview, audit receipts, and testable safety denial for unapproved repo writes.
