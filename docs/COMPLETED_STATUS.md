# X8 Completed Status

Updated on 2026-06-20 for the unsafe-build repair slice.

## Completed In `repair/not-safe-build-yets-x8`

- Corrected target repository to `otiseduncan/X-8`.
- Confirmed PR #44 and PR #45 are not X8 pull requests and were not merged into X8.
- Tightened kernel lane precedence so self-build remains first, GitHub create/connect/pull/push/status resolve before general code/artifact language, and GitHub publish language routes to the GitHub push lane.
- Tightened frontend intent precedence so GitHub Ops resolves before artifact preview routing.
- Hardened GitHub Ops path handling so operations accept workspace-relative paths only. Windows drive paths, host absolute paths, network-share style paths, and root absolute paths are blocked before any git operation.
- Made GitHub push preview safer when a repo has no remote: it returns an empty commit list and `allowed_after_approval: false` instead of pretending a push is ready.
- Added backend regression tests for kernel precedence, GitHub host-path rejection, and read-only push preview behavior.

## Remaining Proof Required Before Pulling Into Main

These are validation gates, not design blockers:

```bash
docker compose -f compose.yaml config
docker compose -f compose.yaml build
docker compose -f compose.yaml run --rm architecture-guard
docker compose -f compose.yaml run --rm api-tests
docker compose -f compose.yaml run --rm web-tests
docker compose -f compose.yaml run --rm e2e-tests
```

Do not claim the local Windows/Docker/browser stack is fully proven until those commands pass on the X8 machine.
