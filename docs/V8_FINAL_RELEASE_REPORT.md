# V8 Final Release Report

Date: 2026-06-20

## Result

V8 functional beta readiness is verified for the local Docker-first assistant cockpit. The final gauntlet passed after fixes.

V8 can chat, show honest integration status, manage Brain/Memory state, propose and apply approved self-build patches, and build/write a generated project into the approved sandbox path.

## Implemented

- Expanded `/api/integrations` into a unified truth model with `live`, `reason`, `required_config`, `safe_actions`, `blocked_actions`, `last_checked`, and receipt metadata.
- Locked operator boundaries for read-only inspection, approval-gated mutation, blocked arbitrary shell, blocked broad remote control, and disabled automatic commit/push.
- Expanded self-build proposal classification and bounded non-empty proposal generation for `ui_feature`, `api_feature`, `test_only`, `docs_only`, `config_change`, `repair_patch`, and `project_builder_feature`.
- Added a guarded Project Builder MVP:
  - preview manifest before writes,
  - exact `manifest_hash` plus `approved=true` required for write,
  - sandbox-only output under `runtime/generated-projects`,
  - generated `manifest.json`, `README.md`, `index.html`, `src/main.js`, and `src/styles.css`.
- Added Developer Cockpit Project Builder UI controls for preview/write proof.
- Hardened Brain/Memory and continuity display so pending/secret/continuity data stays compact and does not duplicate or leak sensitive text.
- Added deterministic blocking for token/private-key-like chat prompts before model generation.

## Verified

| Command | Result |
| --- | --- |
| `docker compose config` | PASS |
| `docker compose build` | PASS |
| `docker compose run --rm architecture-guard` | PASS, preferred-size warnings only |
| `docker compose run --rm api-tests` | PASS, 154 passed, 1 warning |
| `docker compose run --rm web-tests` | PASS, 47 passed |
| `docker compose run --rm e2e-tests` | PASS, 15 passed |
| `docker compose run --rm api-tests pytest tests/test_release_v8_contracts.py tests/test_self_build_contracts.py -q` | PASS, 28 passed |
| `docker compose run --rm api-tests pytest tests/test_chat_truth_contracts.py tests/test_brain_v1_contracts.py tests/test_release_v8_contracts.py -q` | PASS, 78 passed |
| `docker compose run --rm api-tests python /workspace/scripts/project-builder-release-proof.py` | PASS, wrote proof project |

## Project Builder Proof

Output path:

`runtime/generated-projects/v8-release-proof-project`

Files verified:

- `manifest.json`
- `README.md`
- `index.html`
- `src/main.js`
- `src/styles.css`

The proof script reported `status: written` and no missing files.

## Capability Status

- Integration status is honest: optional services such as SearXNG and ComfyUI are not reported live unless configured/reachable.
- Memory works end-to-end through manual remember/retrieve/forget, pending approval, approval/rejection, auto-capture toggle, duplicate prevention, redaction, and compact receipt cards.
- Operator actions are safely bounded: arbitrary shell, broad remote control, external sends, and automatic commit/push are blocked or approval-gated.
- Self-build requires proposal, approval id, patch id, exact patch hash, and unchanged before-hashes before apply.

## Blocked Or External Dependencies

- SearXNG and ComfyUI remain optional/not live unless their compose profiles and runtime services are configured and running.
- Cloud/server-side Google TTS remains unavailable without credentials; browser speech remains the local fallback.
- Ollama/model readiness depends on the configured local/host Ollama endpoint and installed models.
- `docker compose config` expanded a local GitHub token value from environment for `x8-api`. The report does not include the token, but local secret hygiene should move that value out of casual compose output paths before wider sharing.

## Remaining Post-Beta Work

- Split large preferred-warning files before they become hard architecture risks.
- Add richer Project Builder templates beyond the MVP static web scaffold.
- Convert integration catalog statuses from deterministic contract entries to live probes where safe and cheap.
- Add more granular UI affordances for unavailable optional integrations.
