# UI-OP1 Native Operator Cockpit

## Purpose

Move the heavy builder/IDE surface out of the chat lane and into a separate local cockpit window.

- Chat stays on the normal web surface.
- Cockpit runs as a dedicated local web surface.
- Both talk to the same X8 API and approval gates.
- Mirroring becomes fallback/debug only.

## Proposed local ports

- Chat: existing X8 web port, currently `X8_WEB_PORT` / default `5173`.
- Cockpit: `X8_COCKPIT_PORT` / default `6022`.
- API: `X8_API_PORT` / default `8080`.

If Otis aliases the chat surface to `1573`, the same split still applies:

```text
1573 = chat / command lane
6022 = cockpit / builder lane
```

## MVP cockpit instruments

1. Project status strip
   - API health
   - local bridge reachability
   - GitHub status
   - dirty file count

2. File explorer
   - loads from `/api/workspace/files`
   - file click reads through `/api/workspace/read`

3. Code editor surface
   - view/edit selected file text
   - does not mutate on typing

4. Diff / proposal lane
   - proposes changes through `/api/repo/propose-update`
   - applies only through guarded `/api/repo/apply-update` with explicit approval

5. Operation log / terminal substitute
   - shows structured command/status output
   - true shell terminal should be a later protected bridge feature

6. Preview / proof lane
   - shows project previews, receipts, validation summaries, and GitHub status

## Safety rule

The cockpit can view and draft freely. Writes still go through the existing approval model. The first working slice should not introduce unguarded filesystem mutation, shell mutation, Docker mutation, commit, or push.

## Build order

1. Add a separate cockpit web surface on port 6022.
2. Reuse the existing API endpoints for files, reads, diffs, and approvals.
3. Add a chat button/link to open the cockpit window.
4. Replace the old inline DeveloperCockpit toggle with an external cockpit launch once the standalone cockpit is stable.
5. Add a real terminal stream later behind protected operator gates.
