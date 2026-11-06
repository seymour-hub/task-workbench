$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$LogDir = Join-Path $Root "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "server-start.log"
function Write-StartLog([string]$Message) {
    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
}

try {
    Write-StartLog "start-server requested (cwd=$((Get-Location).Path))"

    $existing = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
    if ($existing) {
        Write-StartLog "port 8787 already listening; skip"
        Write-Host "Workbench is already running on http://127.0.0.1:8787"
        exit 0
    }

    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-StartLog "venv missing; creating"
        Write-Host "Creating virtual environment..."
        python -m venv .venv
        .\.venv\Scripts\python.exe -m pip install -U pip
        .\.venv\Scripts\pip.exe install -e "backend[dev]"
    }

    if (-not (Test-Path "web\dist\index.html")) {
        Write-StartLog "web/dist missing; building frontend"
        Write-Host "Building frontend..."
        Push-Location web
        pnpm install
        pnpm build
        Pop-Location
    }

    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    Write-StartLog "starting uvicorn"
    Write-Host "Starting workbench on http://127.0.0.1:8787 ..."
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8787
    Write-StartLog "uvicorn exited with code $LASTEXITCODE"
} catch {
    Write-StartLog "ERROR: $($_.Exception.Message)"
    throw
}
