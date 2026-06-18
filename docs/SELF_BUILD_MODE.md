# XV8 Self-Build Mode

Self-Build Mode lets XV8 inspect its own repository, create a patch plan, create a diff proposal, request approval, and apply only an approved exact patch hash.

Default safety rules:

- no silent file writes
- no arbitrary shell
- no commit by default
- no push by default
- approved root: `/workspace`
- blocked paths include `.env`, `runtime/`, `imports/`, `.git/`, `node_modules/`, build outputs, logs, attachments, and cache folders

API:

- `POST /api/self-build/detect`
- `POST /api/self-build/tasks`
- `GET /api/self-build/tasks/{task_id}`
- `GET /api/self-build/tasks/{task_id}/proposal`
- `POST /api/self-build/tasks/{task_id}/apply`
- `POST /api/self-build/tasks/{task_id}/validate`
- `GET /api/self-build/trust-status`

Allowed validation presets:

- `architecture_guard`
- `api_tests`
- `web_tests`
- `e2e_tests`
- `web_build`
- `compose_config`

Current implementation status:

- Prompt detection: implemented.
- Safe repo context reader: implemented.
- Patch plan: implemented.
- Patch proposal: implemented as deterministic scaffold output with before/after file hashes.
- Approval-bound apply: implemented for exact patch hash and current-file hash match.
- Validation report: implemented through allowlisted Docker/test presets.
- Rollback: implemented for partial write failures during apply.
- Commit/push: not enabled.
- Arbitrary shell: not enabled.
- Broad remote control: not enabled.
