# Avatar Assets

Project-root avatar source assets live here, under `assets/avatar/`.

Served web copies live in `apps/web/public/avatar/` so Vite and Docker can expose
them at `/avatar/...` without reaching outside the web app.

Imported XV7 avatar assets are copied only from the approved `/imports/x7` mount. Runtime import summaries are written under ignored `runtime/import-reports/`.
