# UI-OP4 Host PowerShell Cockpit Action

## Purpose

The cockpit `PowerShell` action means opening a real Windows PowerShell terminal at the selected approved project root. It does not mean adding another always-visible terminal panel inside the browser UI.

## Boundary

The 6022 cockpit remains the project builder surface. The browser can request a terminal, but a browser cannot directly launch arbitrary host programs. Launching PowerShell must go through a local bridge.

## Current implementation

- `GET /api/projects` includes `terminal_path` when a Windows host path is configured for a project.
- `POST /api/local-bridge/open-powershell` requests PowerShell for the selected project.
- The cockpit top bar has a `PowerShell` button.
- The drawer command shortcuts are notes/intent records only until protected command execution is implemented.
- The local bridge exposes `POST /tools/open-powershell`.

## Configuration

For the default X-8 workspace, set the Windows host path:

```env
X8_WORKSPACE_HOST_ROOT=X:/X 8
```

For mounted project folders, set the mounted host catalog root:

```env
X8_PROJECTS_HOST_ROOT=X:/xoduz-projects
```

To use a host-native Windows bridge instead of the Docker bridge container:

```env
X8_LOCAL_BRIDGE_URL=http://host.docker.internal:5788
```

## Honest behavior

If the bridge is still running inside the Linux Docker container, PowerShell launch returns `supported=false` and explains that a host-native Windows bridge is required.

If the selected project has no configured Windows host path, the action returns a blocked receipt and explains which setting is missing.

## Future slice

A future bridge slice should add a one-command Windows host bridge launcher so the cockpit can reliably open:

```powershell
powershell.exe -NoExit -Command "Set-Location -LiteralPath '<project path>'"
```

The cockpit must continue to block unrestricted host-drive browsing and only operate on approved project roots.
