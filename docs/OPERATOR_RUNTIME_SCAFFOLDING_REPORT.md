# Operator Runtime and Self-Build Verification Report

Status: verified scaffold, with limitations documented below.

Implemented scaffolding:

- `apps/api/src/x8/operator/` contracts, planner, runtime, executor, observer, verifier, recovery, risk, approvals, audit, jobs, resources, registry.
- `apps/api/src/x8/operator/tools/` category tool specs.
- `apps/api/src/x8/operator/adapters/` disabled/mock adapter boundaries.
- `apps/api/src/x8/db/` schema-version and table-name scaffolding.
- Operator kill switches in settings and `.env.example`.
- `apps/api/src/x8/self_build/` prompt ingestion, repo context, planning, proposal, validation, approval-bound apply, receipts, audit, manager.
- `POST /api/self-build/tasks` and related self-build API routes.
- Web inline self-build cards for prompt detection, patch plan, patch proposal, and approval-required state.

Not enabled:

- broad remote control
- arbitrary shell
- external sends
- automatic commit
- automatic push
- silent self-modification

Required proof to mark complete:

- API self-build tests pass.
- Web self-build card test passes.
- Architecture guard passes.
- Manual API probe creates a self-build task and does not modify `README.md` before approval.
- A denied apply reports `blocked` and leaves files unchanged.

Validation results:

- API focused tests: `docker compose run --rm api-tests pytest tests/test_api_contracts.py -k "self_build or operator" -q`
- Result: `8 passed, 44 deselected, 1 warning`
- Web tests: `docker compose run --rm web-tests`
- Result: `13 passed`
- Web build: `docker compose run --rm --no-deps x8-web npm run build`
- Result: passed, with Vite chunk-size warning only
- Architecture guard: `docker compose run --rm architecture-guard`
- Result: passed, with preferred-size warnings for `test_api_contracts.py`, `styles.css`, and `App.tsx`
- E2E smoke: `docker compose run --rm e2e-tests`
- Result: `11 passed`
- Self-build e2e: pasted the required self-build prompt, saw prompt-detected, patch-plan, diff-proposal, and approval-required cards.

Manual live self-build proof:

- Prompt used: `Self-build test. Inspect README.md and propose a patch that adds a short Self-Build Mode section. Do not apply the patch until I approve. Do not commit.`
- API route: `POST /api/self-build/tasks`
- Result: task status `planned`
- Patch proposal status: `proposed`
- Approval id created: `sbappr_a039f0aa9dc9`
- Denied apply route: `POST /api/self-build/tasks/{task_id}/apply`
- Apply result: `blocked`
- Applied: `false`
- Reason: `Patch apply denied or not approved.`
- README hash before: `2C6123831453AD17CAC2453F679298F97099E978664B5CCB8036573E6CF6BA8C`
- README hash after: `2C6123831453AD17CAC2453F679298F97099E978664B5CCB8036573E6CF6BA8C`
- File changed before approval: no

Completion claim boundary:

- Self-build scaffold is verified for prompt detection, safe repo context, patch planning, patch proposal, approval-required apply blocking, and UI card rendering.
- Operator runtime is verified as scaffold-only: contracts, routes, capabilities, jobs/approvals/audit surfaces, kill switches, and mock/read-only behavior exist.
- Real broad remote control, arbitrary shell, external sends, automatic commit, and automatic push remain intentionally unavailable.
