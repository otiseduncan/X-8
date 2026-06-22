# UI-OP3 Terminal Drawer

## Goal

Keep the 6022 cockpit usable without overcrowding it. The terminal must be available when needed, but it should not permanently consume editor, file-tree, preview, or diff space.

## Implemented slice

The cockpit now uses a bottom utility drawer with these tabs:

- Terminal
- Logs
- Tests
- Git
- Problems

The drawer supports four visual modes:

- `closed` — status strip only
- `peek` — quick command/log glance
- `open` — normal working height
- `max` — large troubleshooting view

The drawer replaces the earlier permanent terminal/log grid panel.

## Current safety posture

This slice does **not** enable unrestricted shell execution.

The Terminal tab includes safe command shortcuts, but they currently record the intended command into the operation log instead of executing it. This is intentional until a protected local command bridge endpoint exists.

## Required follow-up before live execution

Before typed or button-driven terminal execution is enabled, add a protected bridge contract with:

1. Approved project root enforcement.
2. Explicit allowlist for read-only commands.
3. Protected confirmation for mutating commands.
4. Output size/time limits.
5. Honest command receipts showing command, cwd, exit code, duration, fallback status, and whether mutation was possible.
6. Tests proving destructive commands are blocked unless protected approval is present.

## Suggested safe command tier

Initial command buttons may include:

```powershell
git status --short --branch
git diff --stat
docker compose ps
docker compose logs --tail=120 x8-api x8-cockpit
docker compose run --rm web-tests
docker compose run --rm api-tests
docker compose run --rm architecture-guard
```

## Rule

Chat on 5173 should stay conversational. The 6022 cockpit owns project operation. The terminal belongs in a drawer or popout, not as a permanent always-visible panel.
