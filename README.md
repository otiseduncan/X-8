# XV8 / X-8

XV8 is a Docker-first AI assistant and development-team platform. It is a clean-room rebuild focused on modular manager contracts, honest capability status, senior team seed knowledge, safe development workflows, and artifact preview before repo mutation.

## Requirements

- Docker
- Docker Compose
- Git

No host Python, Node, npm, pnpm, Playwright, PostgreSQL, Redis, or Ollama install is required.

## Quick Start

```bash
docker compose up --build
```

Open the web app at `http://localhost:5173` and the API at `http://localhost:8080/api/health`.

## Service Map

- `x8-api`: FastAPI backend.
- `x8-web`: React/Vite frontend.
- `x8-postgres`: PostgreSQL runtime database.
- `x8-redis`: Redis-ready queue/cache layer.
- `x8-ollama`: Optional Ollama-compatible model service under the `llm` profile.
- `api-tests`: Backend tests.
- `web-tests`: Frontend tests.
- `e2e-tests`: Playwright smoke tests.
- `architecture-guard`: File-size architecture guard.

## Development Cockpit

The web UI includes a browser-based cockpit with project file tree, search, file viewer, code editor surface, diff panel, click approval modal, Docker preset panel, logs panel, artifact preview, website preview iframe, receipts, capability truth, and team council panels.

MVP backend surfaces include:

- `/api/workspace/files`
- `/api/workspace/search`
- `/api/workspace/read`
- `/api/repo/propose-update`
- `/api/repo/apply-update`
- `/api/approvals/request`
- `/api/approvals/decision`
- `/api/docker/presets`
- `/api/docker/run-preset`
- `/api/github/status`
- `/api/github/repository`
- `/api/github/branches`
- `/api/github/commits`
- `/api/local-bridge/status`

## Validation

```bash
docker compose config
docker compose build
docker compose run --rm architecture-guard
docker compose run --rm api-tests
docker compose run --rm web-tests
docker compose run --rm e2e-tests
```

## Capability Truth Model

Every capability reports one of:

- `implemented`
- `disabled`
- `stubbed`
- `unavailable`
- `blocked`

Future email, SMS, calendar, contacts, GitHub, browser, local bridge, Docker, shell, filesystem, notification, and remote access adapters exist as contracts but do not claim live access unless wired and approved.

GitHub is an MVP adapter. Without `GITHUB_TOKEN`, it reports `not_configured` and `capability: unavailable`. With credentials, it can query repository metadata, branches, recent commits, changed files, and file contents.

## Security And Approval

XV8 defaults to look first, inspect without asking, show diffs before applying, click approval before mutation, and receipts after actions. Routine read-only work does not require approval. No automatic commits, pushes, shell mutation, Docker mutation, email, SMS, or remote control occur without explicit approval.

## Legacy Import Sources

XV8 mounts approved legacy sources read-only:

- `X:\XV7\xv7` -> `/imports/x7`
- `X:\X-V-6.1` -> `/imports/x6`

The setup wizard endpoint `/api/config-import/legacy/status` reports X6 and X7 independently. Redacted runtime-only reports are written under `runtime/import-reports/`.

## Architecture Guard

`scripts/check_file_size.py` enforces:

- Normal source hard max: 1,000 lines.
- Preferred warning threshold: 500 lines.
- Large docs or seed files hard max: 1,500 lines.
- No baseline oversized escape hatch.

## Troubleshooting

Use Docker-only diagnostics:

```bash
docker compose ps
docker compose logs x8-api
docker compose logs x8-web
docker compose run --rm architecture-guard
```

## Self-Build Mode

XV8 can inspect its own repo and propose guarded patches. File changes require approval before apply.
