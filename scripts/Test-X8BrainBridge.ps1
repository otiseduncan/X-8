$ErrorActionPreference = "Stop"
$BaseUrl = "http://localhost:8080"
Write-Host "== X8 Brain Bridge Validation =="
$health = Invoke-RestMethod -UseBasicParsing "$BaseUrl/api/brain/health?probe=true"
$health | ConvertTo-Json -Depth 20
if (-not $health.ok) { exit 1 }
$diag = Invoke-RestMethod -UseBasicParsing "$BaseUrl/api/models/bridge-chat-diagnostics?prompt=Reply%20with%20XV8_READY%20only."
$diag | ConvertTo-Json -Depth 20
if (-not $diag.ok) { exit 1 }
Write-Host "PASS"
