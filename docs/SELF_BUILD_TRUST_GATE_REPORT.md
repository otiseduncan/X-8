# XV8 Self-Build Trust Gate Report

## Scope

This report covers the trusted self-build loop in the current `X:\X 8` repo. The loop is designed to let XV8 inspect allowed repo context, propose a patch, wait for exact approval, apply only the approved patch hash, and run allowlisted validation.

## Model Routing Contract

- Normal chat: `qwen3:8b`
- Code/dev help: `qwen3:8b`
- Reasoning/deep planning: `qwen3:14b` only when that lane is requested
- Fallback/light tasks: `qwen3:1.7b`
- Embeddings: `nomic-embed-text:latest`
- Blocked model: `qwen3-coder:30b`

The model status endpoint is light by default. `GET /api/models/status` checks availability without generation; `GET /api/models/status?probe=true` runs the `XV8_READY` health prompt.

## Trust Gate Flow

1. User submits a self-build prompt.
2. XV8 reads only allowlisted repo context.
3. XV8 creates a plan and patch proposal.
4. The proposal contains file paths, unified diff, before hash, after hash, patch hash, risk, tests, and rollback expectations.
5. No files are changed during proposal.
6. Apply requires `approved=true`, matching `patch_id`, matching `approval_id`, and exact `patch_hash`.
7. Apply verifies each target file still matches the proposal `before_hash` before any write.
8. Apply writes exact `proposed_content`, not reconstructed diff text.
9. Apply stores local runtime backups and restores changed files if a partial write fails.
10. Validation is limited to allowlisted presets.

## API Surface

- `POST /api/self-build/detect`
- `POST /api/self-build/tasks`
- `GET /api/self-build/tasks/{task_id}`
- `GET /api/self-build/tasks/{task_id}/proposal`
- `POST /api/self-build/tasks/{task_id}/apply`
- `POST /api/self-build/tasks/{task_id}/validate`
- `GET /api/self-build/trust-status`

## Safety Rules

- Writes without approval: blocked.
- Patch hash mismatch: blocked.
- File changed since proposal: blocked.
- Path outside allowlist: blocked.
- `.env`, `.env.*`, `runtime/`, `imports/`, `.git/`, `node_modules/`, logs, caches, build outputs: blocked.
- Arbitrary shell from prompt: blocked.
- Commit/push by default: blocked.
- `qwen3-coder:30b`: installed-but-blocked if present, never selected.

## Validation Presets

- `architecture_guard`: `docker compose run --rm architecture-guard`
- `api_tests`: `docker compose run --rm api-tests`
- `web_tests`: `docker compose run --rm web-tests`
- `e2e_tests`: `docker compose run --rm e2e-tests`
- `web_build`: `docker compose run --rm --no-deps x8-web npm run build`
- `compose_config`: `docker compose config`

## Proof Status

Current-run validation on June 18, 2026:

- `docker compose build api-tests x8-api x8-web`: passed.
- `docker compose run --rm api-tests`: passed, 58 tests.
- `docker compose run --rm architecture-guard`: passed with preferred-size warnings for `apps/api/tests/test_api_contracts.py`, `apps/web/src/styles.css`, and `apps/web/src/app/App.tsx`.
- `docker compose run --rm web-tests`: passed, 13 tests.
- `docker compose run --rm e2e-tests`: passed, 11 tests.
- `git diff --check`: passed with LF-to-CRLF normalization warnings only.

Focused trust-gate proof:

- Self-build proposal tests prove proposal creation does not write files.
- Apply tests prove denied approval and hash mismatch do not write.
- Apply tests prove files changed after proposal are blocked by `before_hash`.
- Validation tests prove validation reports are recorded.
- Trust-status API test proves the runtime reports approval-hash gating and no writes without approval.
- Model-router test proves a timed-out `qwen3:8b` response can be reported as fallback to `qwen3:1.7b`.

## Current Completion Status

The scaffolding and self-build trust gate are verified by the current command suite above. Live user-machine model reachability still depends on the host Ollama service and installed models being available at the configured Ollama URL.
