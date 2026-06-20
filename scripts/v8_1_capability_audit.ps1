$ErrorActionPreference = "Stop"

$reportPath = "runtime/reports/v8-1-capability-audit.md"
New-Item -ItemType Directory -Force -Path "runtime/reports" | Out-Null

function Get-RepoTextFiles {
  $roots = @("apps", "scripts", "docs", "tests")
  $files = @()

  foreach ($root in $roots) {
    if (Test-Path $root) {
      $files += Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
          $_.Extension -in @(".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".md", ".css", ".json", ".yml", ".yaml")
        }
    }
  }

  return $files
}

$repoFiles = Get-RepoTextFiles

function Search-Repo {
  param([string]$Pattern)

  if (-not $repoFiles -or $repoFiles.Count -eq 0) {
    return @()
  }

  return $repoFiles |
    Select-String -Pattern $Pattern -ErrorAction SilentlyContinue
}

$capabilities = @()

function Add-Capability {
  param(
    [string]$Name,
    [string]$Status,
    [string]$Evidence,
    [string]$Next
  )

  $script:capabilities += [PSCustomObject]@{
    Name = $Name
    Status = $Status
    Evidence = $Evidence
    Next = $Next
  }
}

function Format-Matches {
  param($Matches, [int]$Max = 8)

  if (-not $Matches) {
    return "No matches found"
  }

  return (($Matches | Select-Object -First $Max | ForEach-Object {
    "$($_.Path):$($_.LineNumber)"
  }) -join ", ")
}

Write-Host "Running XV8 V8.1 capability audit..." -ForegroundColor Cyan

# Empty chat / history
$emptyChatHits = Search-Repo "history|session|new chat|conversation|initial"
Add-Capability `
  -Name "Empty-start chat UX" `
  -Status ($(if ($emptyChatHits) { "needs_review" } else { "missing_or_unknown" })) `
  -Evidence (Format-Matches $emptyChatHits 8) `
  -Next "Verify App does not auto-load previous transcript into main chat."

# IDE/code viewer
$ideHits = Search-Repo "diff|file viewer|line number|CodeMirror|monaco|copy|apply patch|artifact"
Add-Capability `
  -Name "IDE/code review surface" `
  -Status ($(if ($ideHits) { "partial_or_present" } else { "missing" })) `
  -Evidence (Format-Matches $ideHits 8) `
  -Next "Need file tree, line-number viewer, copy/edit/apply, diff, artifact cards."

# Project builder
$projectHits = Search-Repo "project builder|generated-projects|sandbox|manifest.json|build project"
Add-Capability `
  -Name "Project Builder" `
  -Status ($(if ($projectHits) { "present_needs_validation" } else { "missing" })) `
  -Evidence (Format-Matches $projectHits 8) `
  -Next "Must prove ADAS prompt routes to Project Builder and writes sandbox files."

# Web research
$researchHits = Search-Repo "searx|research|web search|sources|citation|internet"
Add-Capability `
  -Name "Web research" `
  -Status ($(if ($researchHits) { "partial_or_present" } else { "missing" })) `
  -Evidence (Format-Matches $researchHits 8) `
  -Next "Need honest live/unavailable status and source cards."

# Local system/body
$systemHits = Search-Repo "drive|disk|system status|local bridge|filesystem|cpu|ram|gpu|psutil"
Add-Capability `
  -Name "Local system body/read-only scan" `
  -Status ($(if ($systemHits) { "partial_or_present" } else { "missing" })) `
  -Evidence (Format-Matches $systemHits 8) `
  -Next "Need drive inventory, Docker/Git/Ollama/local bridge status, read-only."

# Email/text
$emailHits = Search-Repo "gmail|email|smtp|sms|text message|twilio|send"
Add-Capability `
  -Name "Email/text drafting/sending" `
  -Status ($(if ($emailHits) { "partial_or_present" } else { "missing" })) `
  -Evidence (Format-Matches $emailHits 8) `
  -Next "Draft allowed. Send must be approval-gated and connector-backed."

# Image generation
$imageHits = Search-Repo "ComfyUI|image generation|generate image|stable diffusion|flux|sdxl"
Add-Capability `
  -Name "Image generation" `
  -Status ($(if ($imageHits) { "partial_or_present" } else { "missing" })) `
  -Evidence (Format-Matches $imageHits 8) `
  -Next "Need backend status, image job API/UI, gallery/output path, no fake generation."

# Decision trace
$traceHits = Search-Repo "decision_trace|selected_route|memories_used|route_confidence"
Add-Capability `
  -Name "Decision trace / brain audit" `
  -Status ($(if ($traceHits) { "present" } else { "missing" })) `
  -Evidence (Format-Matches $traceHits 8) `
  -Next "Keep compact, no chain-of-thought, redact secrets."

# Permission model
$permissionHits = Search-Repo "approval_required|sandbox_write_allowed|preview_only|read_only|blocked|not_configured|disabled"
Add-Capability `
  -Name "Shared permission model" `
  -Status ($(if ($permissionHits) { "partial_or_present" } else { "missing" })) `
  -Evidence (Format-Matches $permissionHits 8) `
  -Next "Normalize action permission states across routes."

# Validation harness
$composeExists = (Test-Path "compose.yaml") -or (Test-Path "docker-compose.yml")
$testDirs = (Test-Path "apps/api/tests") -or (Test-Path "tests") -or (Test-Path "apps/web")
Add-Capability `
  -Name "Validation harness" `
  -Status ($(if ($composeExists -and $testDirs) { "present" } else { "partial" })) `
  -Evidence "Compose exists: $composeExists; test dirs exist: $testDirs" `
  -Next "Run architecture, API, web, e2e after each patch."

$md = New-Object System.Collections.Generic.List[string]

$md.Add("# XV8 V8.1 Capability Audit")
$md.Add("")
$md.Add("Generated: $(Get-Date -Format s)")
$md.Add("")
$md.Add("## Summary")
$md.Add("")

foreach ($cap in $capabilities) {
  $md.Add("### " + $cap.Name)
  $md.Add("")
  $md.Add("- Status: " + $cap.Status)
  $md.Add("- Evidence: " + $cap.Evidence)
  $md.Add("- Next: " + $cap.Next)
  $md.Add("")
}

$md.Add("## Git status")
$md.Add("")
$md.Add("``````text")
$gitStatus = git status --short | Out-String
$md.Add($gitStatus.TrimEnd())
$md.Add("``````")
$md.Add("")

$md.Add("## Recommended next action")
$md.Add("")
$md.Add("Patch in this order:")
$md.Add("")
$md.Add("1. Empty chat start")
$md.Add("2. Project Builder routing failure")
$md.Add("3. IDE/artifact viewer")
$md.Add("4. Local system scan")
$md.Add("5. Research adapter")
$md.Add("6. Image generation status/job surface")
$md.Add("7. Email/text draft and approval-gated send")
$md.Add("8. Full validation")
$md.Add("")

$md | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "Capability audit written to $reportPath" -ForegroundColor Green
Get-Content $reportPath
