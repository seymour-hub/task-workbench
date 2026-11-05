$ErrorActionPreference = "Stop"
$existing = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue

if (-not $existing) {
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$(Join-Path $PSScriptRoot 'start-server.ps1')`""
    )
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        if (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue) {
            break
        }
    }
}

Start-Process "http://127.0.0.1:8787/"
