# Legacy Memory Import From X6 and X7

Approved read-only sources:

- X7: `X:\XV7\xv7` mounted as `/imports/x7`
- X6: `X:\X-V-6.1` mounted as `/imports/x6`

`LegacyBrainImportManager.scan_memory_candidates()` scans both roots independently for memory, brain, preference, workflow, project, model, tool, design, avatar, and verified-status signals.

Import behavior:

- Legacy records are pending candidates only.
- Secrets and secret-like files are redacted.
- Source paths are preserved for review.
- Obvious duplicate previews are deduplicated.
- No legacy record is auto-activated.

Runtime-only reports:

- `runtime/import-reports/legacy-memory-import-summary.md`
- `runtime/import-reports/legacy-memory-import-redacted.json`

Tracked XV8 docs describe the process, but tracked files must never contain extracted API keys, passwords, tokens, private keys, or service-account JSON.
