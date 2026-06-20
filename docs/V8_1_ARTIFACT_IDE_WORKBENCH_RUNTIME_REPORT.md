# V8.1 Artifact IDE Workbench Runtime Report

## Scope Completed
- Upgraded artifact rendering from a lightweight package viewer into a dedicated Artifact IDE Workbench runtime.
- Extracted artifact runtime logic out of the chat-card monolith into a dedicated component.
- Added package-scoped file editing workflow, preview runtime, console/error capture, save/revert semantics, and export fallback flow.
- Updated unit and e2e test coverage to match CodeMirror-based workbench behavior.

## Architecture Changes
- Added a dedicated component:
  - `apps/web/src/app/artifact/ArtifactWorkbench.tsx`
- Integrated the new workbench into chat card rendering:
  - `apps/web/src/app/AssistantComponents.tsx`
- Removed legacy inlined artifact state/body implementation from `AssistantComponents.tsx`.

## Workbench Runtime Capabilities Implemented
- Single package shell with persistent header controls:
  - `Approve`, `Deny`, `Apply`, `Export`
- Top tabs:
  - `Preview`, `Code`, `Files`, `Assets`, `Console`, `Metadata`, `History/Log`, `Export`
- File-centric editing:
  - File tree selection
  - Dirty markers
  - CodeMirror editing
  - `Save current file`, `Save draft`, `Revert file`, `Revert package`
- Approval/apply behavior:
  - Apply disabled until approved and package matches approved signature
  - Any post-approval edit invalidates approval and requires re-approval
- Preview runtime:
  - Iframe generated from package file map
  - CSS/JS aggregation from package files
  - Internal page navigation bridge for in-package links
- Console and error capture:
  - Captures `console.log`, `console.warn`, `console.error`
  - Captures window runtime errors and unhandled rejections
  - Clear console action
- Export:
  - Single HTML export
  - Bundled HTML fallback export for multi-file package
  - Honest note: ZIP export is not implemented yet
- Navigation hooks:
  - Highlight target inputs for file path, line, and token
  - `Go to location` action that opens target file and focuses Code tab context

## UI/Styling Updates
- Added workbench-specific layout and panel styles in:
  - `apps/web/src/app/chatUsability.css`
- Includes responsive behavior for code/file panes and navigation controls.

## Testing Changes
- Updated `CodeEditor` unit-test mock to support editable behavior.
- Updated artifact unit tests in:
  - `apps/web/src/tests/App.test.tsx`
- Updated artifact e2e flow in:
  - `e2e/tests/artifact-package-viewer.spec.ts`
  - Adapted for CodeMirror interactions instead of textarea-based editing.

## Validation Results
### Targeted
1. `cd apps/web && npm test -- src/tests/App.test.tsx`
- Passed: `47 passed`

2. `docker compose run --rm e2e-tests npx playwright test artifact-package-viewer.spec.ts`
- Passed: `1 passed`

### Full Gates
3. `docker compose run --rm web-tests`
- Passed: `54 passed`

4. `docker compose run --rm e2e-tests`
- Passed: `28 passed`

5. `docker compose build architecture-guard`
- Completed successfully (required to refresh stale image cache)

6. `docker compose run --rm architecture-guard`
- Passed with warnings only (line-length preferred warnings)
- No hard-max failures after refactor and file-length reductions.

## Notes
- Architecture guard initially reported stale hard-max failures from pre-rebuild source. Rebuilding `architecture-guard` image resolved stale checks.
- Existing non-blocking warning about React list keys in BrainMemoryPanel remains unchanged from prior baseline and does not block test gates.
