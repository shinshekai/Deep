# install.ps1 — One-command DEEP launcher for Windows
# Usage: .\install.ps1
# Starts DEEP backend + frontend, opens browser to localhost:3782

param(
    [string]$BackendPort = "8001",
    [string]$FrontendPort = "3782",
    [string]$LMStudioHost = "http://localhost:1234"
)

$ErrorActionPreference = "Continue"
$DeepDir = Split-Path -Parent $PSCommandPath

function Step { Write-Host "[DEEP] $args" -ForegroundColor Cyan }
function Ok   { Write-Host "  [OK] $args" -ForegroundColor Green }
function Warn { Write-Host "  [WARN] $args" -ForegroundColor Yellow }
function Err  { Write-Host "  [ERR] $args" -ForegroundColor Red }

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   DEEP — Document Intelligence      ║" -ForegroundColor Cyan
Write-Host "║   One-Command Installer             ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Prerequisites ──
Step "Checking prerequisites..."

$dockerOk = Get-Command docker -ErrorAction SilentlyContinue
$pythonOk = Get-Command python -ErrorAction SilentlyContinue
$nodeOk = Get-Command node -ErrorAction SilentlyContinue
$useDocker = $false

if ($dockerOk) {
    Ok "Docker found: $(docker --version)"
    $useDocker = $true
} elseif ($pythonOk -and $nodeOk) {
    Ok "Python: $(python --version) | Node: $(node --version)"
} else {
    Err "Install Docker Desktop or Python 3.12+ with Node 20+"
    exit 1
}

# ── LM Studio ──
Step "Checking LM Studio..."
try {
    $null = Invoke-WebRequest -Uri "$LMStudioHost/v1/models" -TimeoutSec 5 -UseBasicParsing
    Ok "LM Studio reachable at $LMStudioHost"
} catch {
    Warn "LM Studio not reachable at $LMStudioHost"
    Warn "Install from https://lmstudio.ai or set LM_STUDIO_HOST env var"
}

# ── .env ──
Step "Generating .env configuration..."
$envPath = Join-Path $DeepDir ".env"
if (-not (Test-Path $envPath)) {
    $token = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 43 | ForEach-Object { [char]$_ })
    @"
WS_AUTH_TOKEN=$token
LLM_HOST=$LMStudioHost
BACKEND_PORT=$BackendPort
FRONTEND_PORT=$FrontendPort
"@ | Set-Content $envPath
    Ok ".env generated with random auth token"
} else {
    Ok ".env already exists"
}

# ── Start ──
if ($useDocker) {
    Step "Starting DEEP with Docker Compose..."
    Set-Location $DeepDir
    docker compose up -d --build
    Ok "Docker containers started"
    Start-Sleep -Seconds 5
} else {
    Step "Starting backend..."
    $backendJob = Start-Job -ScriptBlock {
        Set-Location $using:DeepDir
        Set-Location backend
        uv run uvicorn app.main:app --host 0.0.0.0 --port $using:BackendPort
    }
    Ok "Backend starting (PID: $($backendJob.Id))"

    Step "Starting frontend..."
    $frontendJob = Start-Job -ScriptBlock {
        Set-Location $using:DeepDir
        Set-Location frontend
        npm run dev -- -p $using:FrontendPort
    }
    Ok "Frontend starting (PID: $($frontendJob.Id))"
}

# ── Health check ──
Step "Waiting for backend..."
for ($i = 0; $i -lt 30; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$BackendPort/api/v1/health" -TimeoutSec 2 -UseBasicParsing
        Ok "Backend is ready!"
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

# ── Info ──
$token = ""
if (Test-Path $envPath) {
    $token = (Select-String -Path $envPath -Pattern "WS_AUTH_TOKEN=(.*)" | ForEach-Object { $_.Matches.Groups[1].Value })
}
Write-Host ""
Write-Host "DEEP is running!" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:$FrontendPort" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:$BackendPort/docs" -ForegroundColor Cyan
Write-Host "  Auth token: $token" -ForegroundColor Yellow
Write-Host ""

# ── Browser ──
Start-Process "http://localhost:$FrontendPort"

Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
if (-not $useDocker) {
    try { Wait-Job -Job $backendJob, $frontendJob } catch {}
}
