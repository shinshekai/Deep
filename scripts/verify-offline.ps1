# verify-offline.ps1 — Air-gapped operation verification for DEEP (Windows)
# Usage: .\scripts\verify-offline.ps1
# Verifies DEEP can function with zero outbound network access.

$ErrorActionPreference = "Continue"
$ReportFile = "offline-verification-report.json"
$Results = @()
$Pass = 0
$Fail = 0

function Report {
    param($Name, $Status, $Detail)
    $Results += @{ test = $Name; status = $Status; detail = $Detail }
    if ($Status -eq "pass") { $script:Pass++ } else { $script:Fail++ }
    Write-Host "  [$Status] ${Name}: $Detail"
}

Write-Host "=== DEEP Air-Gapped Verification ==="
Write-Host ""

# ── Pre-flight ──
Write-Host "--- Pre-flight ---"

$CurlPath = Get-Command curl.exe -ErrorAction SilentlyContinue
if ($CurlPath) {
    Report "curl-available" "pass" "curl found at $($CurlPath.Source)"
} else {
    Report "curl-available" "fail" "curl not found — required for health checks"
}

# ── LM Studio ──
Write-Host ""
Write-Host "--- Local LLM ---"

$LMHost = if ($env:LM_STUDIO_HOST) { $env:LM_STUDIO_HOST } else { "http://localhost:1234" }

try {
    $lmResponse = Invoke-WebRequest -Uri "$LMHost/v1/models" -TimeoutSec 5 -UseBasicParsing
    $lmJson = $lmResponse.Content | ConvertFrom-Json
    Report "lm-studio" "pass" "LM Studio at $LMHost — $($lmJson.data.Count) model(s)"
} catch {
    Report "lm-studio" "fail" "LM Studio not reachable at $LMHost"
}

# ── Network check ──
Write-Host ""
Write-Host "--- Network ---"

try {
    $null = Invoke-WebRequest -Uri "https://google.com" -TimeoutSec 5 -UseBasicParsing
    Report "network-off" "warn" "Internet IS available — not truly air-gapped"
} catch {
    Report "network-off" "pass" "No internet access detected"
}

# ── Backend health ──
Write-Host ""
Write-Host "--- DEEP Backend ---"

$BackendHost = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "http://localhost:8001" }

try {
    $healthResponse = Invoke-WebRequest -Uri "$BackendHost/api/v1/health" -TimeoutSec 5 -UseBasicParsing
    $healthJson = $healthResponse.Content | ConvertFrom-Json
    Report "backend-health" "pass" "Status: $($healthJson.status)"
} catch {
    Report "backend-health" "fail" "Backend not reachable at $BackendHost"
}

try {
    $readyResponse = Invoke-WebRequest -Uri "$BackendHost/api/v1/ready" -TimeoutSec 5 -UseBasicParsing
    $readyJson = $readyResponse.Content | ConvertFrom-Json
    Report "backend-ready" "pass" "Status: $($readyJson.status)"
} catch {
    Report "backend-ready" "fail" "Readiness check failed"
}

# ── Frontend ──
Write-Host ""
Write-Host "--- DEEP Frontend ---"

$FrontendHost = if ($env:FRONTEND_HOST) { $env:FRONTEND_HOST } else { "http://localhost:3782" }

try {
    $frontendResponse = Invoke-WebRequest -Uri "$FrontendHost/" -TimeoutSec 5 -UseBasicParsing
    Report "frontend" "pass" "Frontend responding at $FrontendHost"
} catch {
    Report "frontend" "warn" "Frontend not reachable at $FrontendHost (may not be running)"
}

# ── Summary ──
Write-Host ""
Write-Host "=== Results ==="
Write-Host "Passed: $Pass | Failed: $Fail"

$Report = @{
    timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    passed    = $Pass
    failed    = $Fail
    results   = $Results
}
$Report | ConvertTo-Json -Depth 3 | Set-Content -Path $ReportFile
Write-Host "Report saved to $ReportFile"
