# Mirror rollback to native cockpit

## Decision

The mirrored IDE/screen state is being rolled back. Mirroring may remain as an emergency debug tool, but it should not be the primary builder experience.

## Replacement direction

Use a native operator cockpit instead of a mirrored desktop/IDE surface.

- Chat remains the command lane.
- Cockpit becomes the build/operate lane.
- The cockpit should run as its own local web window.
- The cockpit uses structured API data instead of pixels from a mirrored screen.

## Operating split

```text
Chat surface     -> conversation, planning, approvals, compact summaries
Cockpit surface  -> file tree, editor, diff, preview, logs, repo status, validation
Local API/bridge -> source of truth for files, repo state, Docker, approvals, receipts
```

## Rollback rule

Any UI that only displays a mirrored VS Code, PowerShell, desktop, or browser window should be removed from the primary workflow. If kept, it must be labeled fallback/debug and not be treated as proof that Xoduz can operate the project.

## MVP replacement behavior

The first native cockpit does not need every IDE feature. It needs enough to make Xoduz useful as a builder:

1. view workspace file tree
2. open/read files
3. edit drafts in a code editor
4. produce guarded diffs
5. require approval before write
6. show operation receipts
7. show structured logs/status
8. open in a separate local browser window

## Out of scope for the first replacement slice

- raw remote desktop mirroring
- unguarded shell execution
- unguarded filesystem writes
- automatic commits or pushes
- pretending terminal output is live if it is not connected to the operator bridge
