# UI-OP2 Native Cockpit Project Manager

## Purpose

The `6022` cockpit is the project operating surface. It must be able to switch projects without returning to mirroring or exposing the whole host drive.

## Current implementation

UI-OP2 adds a guarded project-selection layer:

- `GET /api/projects` returns approved project roots.
- The default X-8 workspace remains available as project `x8`.
- Mounted directories under `/projects` are discovered as selectable projects.
- Optional `X8_APPROVED_PROJECT_ROOTS` entries can register additional approved roots.
- Workspace list/read actions accept `project_id`.
- Repo propose/apply update actions accept `project_id`.
- The `6022` cockpit includes a project selector, project detail bar, close-project control, Open Project guidance, and Save reviewed draft control.

## Safety rule

Xoduz can only read/write inside the selected approved project root. Unrestricted host-drive browsing is intentionally not part of this slice.

## Project root sources

1. Default workspace root:

```txt
/workspace
```

2. Mounted project catalog:

```txt
/projects/<project-folder>
```

3. Optional configured roots using `X8_APPROVED_PROJECT_ROOTS`:

```txt
id::Display Name::/container/path::kind;another::Another Project::/container/other::repo
```

## Docker project catalog

Compose mounts this catalog path for the API:

```yaml
${X8_PROJECTS_HOST_ROOT:-./runtime/projects}:/projects
```

For a Windows host project folder, set this in a local `.env` file:

```txt
X8_PROJECTS_HOST_ROOT=X:/xoduz-projects
```

Then place projects under:

```txt
X:\xoduz-projects\
  X-8\
  xoduz-sandbox\
  DriveOps-IQ\
```

After restarting the API/cockpit containers, the folders appear in the cockpit project dropdown.

## Current scope

Implemented now:

- select approved project
- close current project
- list files for selected project
- read files from selected project
- edit existing files
- propose diff
- save only after reviewed diff and browser confirmation

Queued follow-ups:

- create new file
- create new folder
- rename file
- delete file with stronger confirmation
- host bridge assisted Open Folder registration
- live terminal streaming behind protected bridge gates

## Validation

```powershell
docker compose -f .\compose.yaml config --services | Select-String 'cockpit|api'
docker compose -f .\compose.yaml up --build x8-postgres x8-redis x8-api x8-web x8-cockpit
```

Open:

```txt
Chat:    http://localhost:5173/
Cockpit: http://localhost:6022/
```

Expected cockpit behavior:

- Project dropdown shows X-8.
- Mounted `/projects` children appear when `X8_PROJECTS_HOST_ROOT` is set and contains folders.
- Switching project refreshes the file list.
- Saving a file requires Propose diff first.
- Apply is blocked if the editor changed after the diff was proposed.
