# X8 Production Readiness Status

Date: 2026-06-20
Branch: `cleanup/test-speed-and-readiness-x8`
Base: `main` after merged repair PR #1

## Current readiness

X8 is repair-stable and ready for the next build slice, but she is not production-ready yet.

The merged repair proved the critical runtime path that was blocking forward progress:

- Docker-first build path is usable.
- Architecture guard passes the 1000-line hard ceiling.
- API contract suite passes locally.
- Web unit suite passes locally.
- Browser e2e suite passes locally.
- Kernel mode-resolution precedence now protects GitHub, self-build, artifact, Brain, and general routes from stealing each other.
- GitHub Ops path handling rejects host/Windows/absolute/network paths instead of treating them as workspace-relative mutation targets.
- GitHub push preview is honest when no remote exists.
- Brain continuity and semantic retrieval contracts are stable enough to build on.

## Not production-ready yet

Before external production use, X8 still needs:

1. CI gates that run the same Docker proof on every PR.
2. Secret-handling cleanup: do not print or expose live tokens through config/debug output.
3. Deployment hardening: TLS/reverse proxy, restart policy, health checks, backup/restore, and rollback path.
4. Observability: runtime logs, audit events, failed-tool visibility, model/fallback status, and e2e artifacts.
5. File-size cleanup: keep all source files below the 1000-line hard ceiling and reduce near-limit files before feature growth.
6. Test-speed split: keep fast feedback under 30 seconds where possible and reserve full browser proof for pre-merge/final validation.

## Fast test tiers

Use the full suite before merges:

```powershell
docker compose -f compose.yaml run --rm architecture-guard
docker compose -f compose.yaml run --rm api-tests
docker compose -f compose.yaml run --rm web-tests
docker compose -f compose.yaml run --rm e2e-tests
```

Use targeted e2e tiers during repair loops:

```powershell
docker compose -f compose.yaml run --rm e2e-fast-tests
docker compose -f compose.yaml run --rm e2e-brain-tests
docker compose -f compose.yaml run --rm e2e-self-build-tests
```

The full e2e suite remains the source of truth. The targeted tiers are for faster iteration only.

## Near-term cleanup targets

Prioritize these before heavy new feature work:

- `apps/web/src/app/App.tsx`
- `apps/web/src/tests/App.test.tsx`
- `apps/web/src/styles.css`
- `apps/api/src/x8/brain/memory_store.py`
- `apps/api/src/x8/brain/memory_manager.py`
- `apps/api/tests/test_brain_v1_contracts.py`
- `apps/api/tests/test_api_contracts.py`
- `e2e/tests/smoke.spec.ts`

## Merge policy

A branch is merge-ready only after:

1. Architecture guard passes with no hard failures.
2. API tests pass.
3. Web tests pass.
4. Full e2e passes.
5. Any new warning above 500 lines is either reduced or documented.
6. Any exposed token is revoked/rotated before the proof is considered clean.
