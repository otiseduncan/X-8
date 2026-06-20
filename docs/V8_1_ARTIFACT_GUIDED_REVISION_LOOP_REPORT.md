# V8.1 Artifact Guided Revision Loop Report

## Previous Behavior
- The bridge could locate code and perform some direct edits.
- Follow-up revision intent after locate prompts was not consistently treated as a pending sandbox revision response.
- Diff/history entries were not structured as red/green revision records for guided loop edits.
- Active artifact follow-up commands were improving, but not yet modeled as a full guided revision state machine.

## New Guided Revision Behavior
- Added a guided revision loop with explicit workbench state transitions:
  - idle
  - locating
  - awaiting_revision_instruction
  - editing_sandbox
  - preview_refreshed
  - awaiting_approval
  - approved
  - applied
- Locate/question prompts now:
  - select the target file
  - focus Code tab
  - highlight target lines
  - ask one concise follow-up: "What would you like to change it to?"
  - store pending revision context for the active artifact package
- Pending revision replies (for example, "I want blue") are interpreted as revisions to the active package and applied in-sandbox.
- Direct edit prompts (for example, background/name/button text changes) edit immediately without a second question.
- Follow-up revisions stay inside the same artifact package (no new artifact generation) unless explicit start-over/new-artifact language is used.

## Command/State Contract
- Extended Artifact command type support with guided workflow commands:
  - locate
  - ask_followup
  - apply_pending_revision
  - edit_file
  - refresh_preview
  - show_diff
  - highlight_added_lines
  - highlight_deleted_lines
- Extended artifact workbench snapshot/state contracts with:
  - workbench_state
  - pending_revision
  - revision_history
  - diff_entries
  - last_artifact_command
- Added pending revision context shape with:
  - activeArtifactPackageId
  - target_file_path
  - line_start / line_end
  - token_or_selector
  - current_value
  - revision_kind
  - followup_prompt

## Sandbox Edit Rules
- Active artifact follow-up commands are intercepted locally in the bridge/workbench path.
- Sandbox edits update the active draft package and refresh preview.
- Approval remains required only for external apply/write/export flows.
- Editing after approval invalidates approval and requires re-approval before Apply can be used again.

## Red/Green Diff Behavior
- Workbench now records structured diff entries for bridge edits.
- Diff panel in History/Log shows:
  - added/modified-new lines with green styling
  - deleted/modified-old lines with red styling
- Revision history captures:
  - id/timestamp/summary/file
  - before/after snippets
  - added/deleted/modified line indices
  - approved-state invalidation marker

## Files Updated
- apps/web/src/types/contracts.ts
- apps/web/src/app/artifact/commandBridge.ts
- apps/web/src/app/artifact/ArtifactWorkbench.tsx
- apps/web/src/app/chatUsability.css
- apps/web/src/tests/ArtifactCommandBridge.test.tsx
- e2e/tests/artifact-package-viewer.spec.ts
- apps/web/src/tests/App.test.tsx

## Tests Added/Updated
- Unit: apps/web/src/tests/ArtifactCommandBridge.test.tsx
  - background locate asks + pending context
  - pending answer applies sandbox revision
  - button color locate + pending answer edit
  - website-name locate + pending answer edit
  - direct background edit without follow-up prompt
  - single artifact package continuity
  - red/green diff history assertions
  - approval invalidation behavior
  - no Kernel limitations for active artifact revision commands
- Playwright: e2e/tests/artifact-package-viewer.spec.ts
  - guided locate -> answer -> edit loop
  - history diff red/green visibility
  - website-name guided revision
  - approve then edit invalidates Apply until re-approval

## Validation Results
- npm test -- src/tests/ArtifactCommandBridge.test.tsx
  - pass
- docker compose run --rm e2e-tests npx playwright test artifact-package-viewer.spec.ts
  - pass
- docker compose run --rm web-tests
  - pass
- docker compose run --rm e2e-tests
  - pass
- docker compose run --rm architecture-guard
  - pass (warnings only)

## Known Limitations
- Diff generation is line-based and optimized for practical sandbox revision visibility rather than semantic AST diffs.
- Some approval/button assertions in legacy tests required stabilization with wait-based checks due rerender timing.
- Architecture guard currently reports warning-level line-length signals in existing large files.

## Commit Hash
- To be filled after commit creation.
