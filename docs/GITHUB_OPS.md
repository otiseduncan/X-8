# XV8 GitHub Ops

## Environment

GitHub credentials are local runtime configuration only:

```env
X8_GITHUB_TOKEN=
X8_GITHUB_OWNER=otiseduncan
X8_GITHUB_DEFAULT_VISIBILITY=private
```

Do not commit real tokens. Rotate credentials by changing `.env` or the host/container environment and restarting the API container. No code change is required.

## Auth Status

`GET /api/github/ops/auth-status` reports:

- token configured true/false
- owner configured true/false
- owner
- default visibility

The token value is never returned.

## Local Repo Status

`GET /api/github/ops/status` inspects the configured workspace only. It reports repo state, branch, sanitized origin remote, dirty state, changed files, last commit, and ahead/behind when upstream exists.

## Preview Workflows

Read-only previews:

- `POST /api/github/ops/push-preview`
- `POST /api/github/ops/pull-preview`

Preview routes do not run `git push` or `git pull`.

## Approval-Gated Workflows

All write operations require `approved=true`:

- `POST /api/github/ops/init`
- `POST /api/github/ops/connect-remote`
- `POST /api/github/ops/create-repo`
- `POST /api/github/ops/pull`
- `POST /api/github/ops/push`

Requests without approval return `blocked`. Remote URLs containing credentials are rejected. GitHub repo creation uses the configured token for the API call but never places the token in the returned data or remote URL.

## Create Repo

Send `repo_name`, optional `owner`, optional `visibility`, and `approved=true`. Visibility must be `private` or `public`; default is `X8_GITHUB_DEFAULT_VISIBILITY`.

## Connect Remote

Send `remote_url`, `path`, and `approved=true`. Use normal HTTPS or SSH remotes, never token-in-URL remotes.

## Pull And Push

Pull and push are separate approved operations. Self-build patch apply never commits or pushes automatically.

## UI

Settings includes a cyan/neon-blue GitHub Ops panel with auth status, branch, remote, dirty state, changed file count, last commit, ahead/behind, refresh, pull preview, push preview, and approval proposal buttons.
