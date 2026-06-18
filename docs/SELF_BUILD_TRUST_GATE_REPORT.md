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
2. XV8 classifies the self-build intent before doing anything else.
3. Apply/approval intent is only selected when the prompt asks to apply/approve/write and includes approval or patch-hash context; negated phrases such as "do not apply" and "do not write" keep the request read-only or proposal-only.
4. Create-proposal intent wins when the prompt asks to add, build, modify, implement, update, fix, create, wire, or change project behavior/files, even if the prompt mentions trust status, validation reports, patch hashes, or proposal details as feature requirements.
5. Read-only intents such as "show proposal details", "show latest proposal", "show patch hash", "show approval id", "show validation report", "show trust status", "before approval", "do not apply", "do not write anything yet", "no files should be changed", "what is the current proposal", and "list proposal ids" retrieve existing data only when the prompt does not ask to add/build/modify files.
6. Trust status intent applies only to direct requests to show the current trust status, not to build requests that add a trust-status UI/card.
7. Validation report intent applies only to direct requests to show the latest validation report, not to build requests that include validation report requirements.
8. For create-proposal intent, XV8 reads only allowlisted repo context.
9. XV8 creates a plan and patch proposal.
10. The proposal contains file paths, unified diff, before hash, after hash, patch hash, risk, tests, and rollback expectations.
11. No files are changed during proposal.
12. Apply requires `approved=true`, matching `patch_id`, matching `approval_id`, and exact `patch_hash`.
13. Apply verifies each target file still matches the proposal `before_hash` before any write.
14. Apply writes exact `proposed_content`, not reconstructed diff text.
15. Apply stores local runtime backups and restores changed files if a partial write fails.
16. Validation is limited to allowlisted presets.

## API Surface

- `POST /api/self-build/detect`
- `POST /api/self-build/tasks`
- `GET /api/self-build/tasks/{task_id}`
- `POST /api/self-build/prompt`
- `GET /api/self-build/tasks/latest/proposal`
- `GET /api/self-build/tasks/latest/validation`
- `GET /api/self-build/tasks/{task_id}/proposal`
- `POST /api/self-build/tasks/{task_id}/apply`
- `POST /api/self-build/tasks/{task_id}/validate`
- `GET /api/self-build/trust-status`

## Real Proposal Generation

The proposal engine no longer defaults create requests to `README.md`. It classifies the requested task, reads the matching allowlisted source files, and generates deterministic proposed content for supported task types. The trust-status UI feature now produces frontend source diffs instead of documentation-only output.

For the supported trust-status UI feature, the proposal targets:

- `apps/web/src/services/apiClient.ts`
- `apps/web/src/app/App.tsx`

The generated patch adds a `loadSelfBuildTrustStatus()` API helper and a visible `Self-build trust gate` runtime card that displays approval gating, hash gating, write/commit/push defaults, validation preset count, validation presets, and allowed/blocked path counts. The patch remains proposal-only until exact approval.

For trust-status UI prompts, proposal validation now requires visible JSX containing `Self-build trust gate` and `Validation preset count`. API fetch/state wiring without visible render output is blocked and receives no approval id.

## No-Op Proposal Rejection

A proposal is invalid if no real code changes are generated. Validation fails when:

- no changes are present
- a change has an empty unified diff
- `before_hash` equals `after_hash`
- `proposed_content` matches the current file content
- a UI feature wires API/state but does not render a visible card or label

No-op proposals are blocked, receive no `approval_id`, set `apply_safe=false`, and return the message `No code changes were generated.` The UI does not render an Apply approval card for blocked/no-op proposals.

## Real Proposed Content Requirement

Patch hashes are computed from file path, before hash, after hash, unified diff, and proposed content. Latest proposal details include safe proposed-content previews so Otis can inspect what would be written before approving the exact hash.

UI feature proposals include frontend validation presets by default: `architecture_guard`, `web_tests`, and `web_build`.

## Task Classification

Self-build create requests are classified as:

- `ui_feature`
- `api_feature`
- `test_only`
- `docs_only`
- `config_change`
- `unknown_safe`

`README.md` is only targeted for explicit docs/readme/documentation prompts. UI feature prompts target `apps/web/src/`. API feature prompts target backend route/manager/test files. Test-only prompts target tests. Unknown-safe prompts produce no generic write proposal and require clarification.

## Read-Only Inspection Behavior

Read-only self-build prompts retrieve existing state and do not create proposals:

- latest proposal details
- trust status
- latest validation report
- patch hash / approval id
- proposal ids

If no proposal exists, proposal inspection returns `No active self-build proposal found.` Latest validation returns a validation-specific missing response when a proposal exists but no validation report has been produced.

## Safety Rules

- Writes without approval: blocked.
- GitHub init/connect/create/pull/push: supervised external operations, separate from self-build patch apply, approval required.
- Read-only inspection prompts creating new proposals: blocked.
- Patch hash mismatch: blocked.
- File changed since proposal: blocked.
- Path outside allowlist: blocked.
- `.env`, `.env.*`, `runtime/`, `imports/`, `.git/`, `node_modules/`, logs, caches, build outputs: blocked.
- Arbitrary shell from prompt: blocked.
- Commit/push by default: blocked.
- `qwen3-coder:30b`: installed-but-blocked if present, never selected.

## Approval/Apply Safety Gates

Apply remains locked behind:

- exact `patch_id`
- exact `approval_id`
- exact `patch_hash`
- unchanged file `before_hash`
- exact proposed content writes
- runtime backups before writes
- rollback on partial write failure

Bad patch hash, bad approval id, bad patch id, and changed target content are all blocked by tests.

## Frontend Trust-Status Proof

The proposed trust-status UI card displays:

- approval required
- hash approval required
- writes without approval
- commit allowed by default
- push allowed by default
- validation presets
- allowed path count
- blocked path count

Proposal cards expose `task_id`, `patch_id`, `approval_id`, `patch_hash`, changed paths, validation status, and diff content. Receipt and approval card rendering now uses payload metadata when available, avoiding blank `{}` detail cards.

## Cyan/Neon Blue UI Standard

Frontend primary accent styling is cyan/neon blue. The old purple/violet/fuchsia/indigo language was removed from frontend source styling, and the web test suite includes a static guard that scans `apps/web/src` source files for blocked cool-purple tokens.

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
- `docker compose run --rm api-tests`: passed, 65 tests.
- `docker compose run --rm architecture-guard`: passed with preferred-size warnings for `apps/api/tests/test_api_contracts.py`, `apps/web/src/styles.css`, and `apps/web/src/app/App.tsx`.
- `docker compose run --rm web-tests`: passed, 13 tests.
- `docker compose run --rm e2e-tests`: passed, 11 tests.
- `git diff --check`: passed with LF-to-CRLF normalization warnings only.

Live proof after app restart on June 18, 2026:

- `docker compose down --remove-orphans`: passed.
- `docker compose up -d --build x8-api x8-web x8-postgres x8-redis x8-local-bridge`: passed.
- `docker compose ps`: `x8-api`, `x8-web`, `x8-postgres`, `x8-redis`, and `x8-local-bridge` were running.
- `GET http://localhost:8080/api/health`: returned `{"status":"ok","service":"x8-api"}`.
- Build prompt mentioning a trust-status UI feature returned `intent=create_proposal`, `task_id=task_5aeef69fa07f`, `patch_id=patch_52fdcd76649a`, `approval_id=sbappr_df8919d5b8d4`, and `patch_hash=df8919d5b8d40cc9e843560d34472c6dbd7b579f5f924af02152b8997b1c88cf`.
- Read-only prompt "Show the full latest self-build patch proposal details before approval. Do not create a new proposal. Do not apply. Do not write anything." returned `intent=inspect_proposal` with the same `task_id`, `patch_id`, `approval_id`, and `patch_hash`.
- `README.md` SHA256 after both live prompts was `2c6123831453ad17cac2453f679298f97099e978664b5ccb8036573e6cf6ba8c`, matching the proposal `before_hash`; no file write occurred.

Current hardening live proof after restart on June 18, 2026:

- Build prompt for a trust-status UI feature returned `intent=create_proposal`, `task_type=ui_feature`, `task_id=task_b3fd89695011`, and `patch_id=patch_705d541b4c89`; `approval_id` and `patch_hash` were present.
- Changed paths were `apps/web/src/app/App.tsx` and `apps/web/src/services/apiClient.ts`; `README.md` was not targeted.
- The proposal returned `validation_status=passed`, `apply_safe=true`, `tests_to_run=architecture_guard, web_tests, web_build`, non-empty diffs, and `before_hash != after_hash` for every changed file.
- The proposed diff included visible JSX containing `Self-build trust gate` and `Validation preset count`.
- The proposed diff included cyan styling through `#22d3ee` and did not include purple/violet/fuchsia/indigo tokens.
- `GET http://localhost:8080/api/self-build/tasks/latest/proposal` returned the same `task_id` and `patch_id`, non-empty diffs, changed hashes, visible JSX, and `apply_safe=true`.
- Actual `apps/web/src/app/App.tsx` did not contain `Self-build trust gate` after proposal creation; no source file was written before approval.

No-op rejection live proof after restart on June 18, 2026:

- Controlled trust-status UI prompt returned `intent=create_proposal`, `task_type=ui_feature`, `task_id=task_82549e07fe2c`, `patch_id=patch_62571ddc2f67`, `approval_id=sbappr_88892ae36c68`, and `patch_hash=88892ae36c685dd3797464f656d3668e990c7cb5ee88bb021cbb0df9e2795220`.
- Changed paths were `apps/web/src/app/App.tsx` and `apps/web/src/services/apiClient.ts`.
- All proposal changes had `before_hash != after_hash`.
- All proposal changes had non-empty unified diffs.
- Latest proposal endpoint returned the same non-empty diffs and changed hashes.
- Actual `apps/web/src/app/App.tsx` and `apps/web/src/services/apiClient.ts` file hashes stayed unchanged before approval.

Focused trust-gate proof:

- Self-build proposal tests prove proposal creation does not write files.
- Apply tests prove denied approval and hash mismatch do not write.
- Apply tests prove files changed after proposal are blocked by `before_hash`.
- Validation tests prove validation reports are recorded.
- Trust-status API test proves the runtime reports approval-hash gating and no writes without approval.
- Model-router test proves a timed-out `qwen3:8b` response can be reported as fallback to `qwen3:1.7b`.
- Intent tests prove proposal inspection, trust status, and validation report prompts do not create new proposals.
- Intent tests prove a build prompt that mentions trust status as the feature still creates a proposal.
- Latest proposal tests prove read-only details return the original proposal `task_id`, `patch_id`, `approval_id`, and `patch_hash`.
- Proposal-generation tests prove the trust-status UI feature targets `apps/web/src/`, does not target `README.md`, and includes non-empty code diffs.
- No-op tests prove empty/equal-content proposals are blocked, not apply-safe, and do not receive an approval id.
- No-visible-render tests prove UI feature proposals are blocked when they only add API/state wiring.
- Patch-hash tests prove changing proposed content changes the computed patch hash.
- Apply tests prove exact approval writes exact proposed content in a temp workspace.
- Web tests prove proposal cards expose metadata and frontend source is free of blocked cool-purple tokens.

## Remaining Risks

- Host Ollama availability depends on the local machine and configured Ollama URL.
- Self-build is supervised, not autonomous.
- No broad remote control is enabled.
- No auto-push is enabled.
- User approval is still required for writes.
- Proposal generation is deterministic for supported task types and should expand task coverage over time.

## Current Completion Status

The self-build trust gate and deterministic trust-status UI proposal path are verified by tests. Live proof must be rerun after each hardening change before claiming runtime behavior is current.
