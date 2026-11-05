$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$existing = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Workbench is already running on http://127.0.0.1:8787"
    exit 0
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -U pip
    .\.venv\Scripts\pip.exe install -e "backend[dev]"
}

if (-not (Test-Path "web\dist\index.html")) {
    Write-Host "Building frontend..."
    Push-Location web
    pnpm install
    pnpm build
    Pop-Location
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Starting workbench on http://127.0.0.1:8787 ..."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8787
