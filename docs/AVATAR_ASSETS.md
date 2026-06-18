# Avatar Assets

XV8 uses three shipped avatar video clips from `apps/web/public/avatar`.

| State | File | Size | Notes |
| --- | --- | ---: | --- |
| idle | `xoduz-idle.mp4` | 5,830,669 bytes | Default waiting/muted/error fallback clip. |
| thinking/listening | `xoduz-thinking.mp4` | 2,368,060 bytes | Used for thinking and as the listening clip because no separate listening file exists. |
| speaking | `xoduz-speaking.mp4` | 3,404,043 bytes | Used while browser TTS is speaking. |

The clips were moved from `assets/avatar` into the web public avatar folder so Docker/Vite can serve them at `/avatar/...` without referencing files outside the web app.

Total video payload is about 11.6 MB. That is acceptable for local XV8 development, but if the repository later gains many more generated clips or higher-resolution video, move avatar videos to Git LFS or a documented local asset package.

Fallback behavior:

- `idle` uses `xoduz-idle.mp4`.
- `listening` uses `xoduz-thinking.mp4`, then falls back to idle.
- `thinking` uses `xoduz-thinking.mp4`, then falls back to idle.
- `speaking` uses `xoduz-speaking.mp4`, then falls back to idle.
- `muted` and `error` use idle with a visible state badge.
- If video loading fails, the UI falls back to idle, then to `/avatar/fallback.svg`.
