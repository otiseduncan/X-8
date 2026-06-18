# Legacy Config Import From X6 And X7

XV8 imports legacy configuration from two read-only sources:

- X7 / XV7 source: `X:\XV7\xv7` mounted at `/imports/x7`
- X6 source: `X:\X-V-6.1` mounted at `/imports/x6`

X7 is preferred for GitHub, cockpit, IDE/operator, safe writer, avatar, speech, local bridge, and assistant/runtime patterns.

X6 is preferred for ComfyUI, Juggernaut model paths, workflows, SearXNG/search settings, image generation, older provider keys, and older service patterns.

Reports are runtime-only:

- `runtime/import-reports/x7-config-import-redacted.json`
- `runtime/import-reports/x6-config-import-redacted.json`
- `runtime/import-reports/legacy-config-import-summary.md`

Secrets are never written to tracked files and only redacted previews are shown.
