$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -U pip
    .\.venv\Scripts\pip.exe install -e "backend[dev]"
}

if (-not (Test-Path "web\node_modules")) {
    Push-Location web
    pnpm install
    Pop-Location
}

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$env:PYTHONUTF8='1'; Set-Location '$Root'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8787 --reload"
)

Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root\web'; pnpm dev"
)

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:5173/"
