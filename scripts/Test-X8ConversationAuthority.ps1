param(
    [string]$ComposeFile = "compose.yaml"
)

$ErrorActionPreference = "Stop"

Write-Host "X8 conversation authority proof" -ForegroundColor Cyan
Write-Host "Running focused API tests for routing, prompt contract, and context boundary..." -ForegroundColor Cyan

docker compose -f $ComposeFile run --rm --build api-tests python -m pytest `
    tests/test_conversation_readiness.py `
    tests/test_conversation_authority.py `
    tests/test_kernel_authority_boundaries.py `
    tests/test_prompt_authority_contract.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Conversation authority proof failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Conversation authority proof completed." -ForegroundColor Green
