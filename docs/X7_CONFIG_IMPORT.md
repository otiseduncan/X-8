# Legacy Config Import

XV8 scans approved read-only import paths: `/imports/x7` and `/imports/x6`.

The intended local mounts are:

- `X:\XV7\xv7` -> `/imports/x7`
- `X:\X-V-6.1` -> `/imports/x6`

The importer writes redacted runtime-only reports to:

- `runtime/import-reports/x7-config-import-redacted.json`
- `runtime/import-reports/x6-config-import-redacted.json`
- `runtime/import-reports/legacy-config-import-summary.md`

Secrets are never printed in full, committed, or written into tracked files.
