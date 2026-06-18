# Legacy Brain Context Import

XV8 imports legacy brain/context lessons only as redacted, structured candidate context. It must not copy XV7/X6 monoliths, runtime logs, or secrets into tracked knowledge.

Approved sources:

- X7/XV7: `X:\XV7\xv7` mounted at `/imports/x7`
- X6: `X:\X-V-6.1` mounted at `/imports/x6`

Runtime-only reports:

- `runtime/import-reports/legacy-brain-import-summary.md`
- `runtime/import-reports/legacy-brain-import-redacted.json`

Import rules:

- Candidate files are limited to text-like brain, memory, knowledge, prompt, context, persona, receipt, and model records.
- Secret-like files are represented as `[redacted secret-like file]`.
- Runtime logs are not promoted to knowledge.
- Useful records must remain separated by context source type before they are eligible for kernel injection.
- Missing import paths are reported as limitations instead of fake success.

The initial `LegacyBrainImportManager` is intentionally conservative. It produces redacted discovery reports; promotion into tracked XV8 seed knowledge should be a separate reviewed step.
