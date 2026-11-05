param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Url = "http://127.0.0.1:8787/"
$HealthUrl = "http://127.0.0.1:8787/api/health"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$LogFile = Join-Path $Root "data\logs\workbench.log"

function Test-Workbench {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (-not (Test-Workbench)) {
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"

    # Hidden console window; the app logs to data\logs\workbench.log.
    Start-Process `
        -FilePath $Python `
        -ArgumentList @(
            "-m", "uvicorn", "app.main:app",
            "--app-dir", "backend",
            "--host", "127.0.0.1",
            "--port", "8787"
        ) `
        -WindowStyle Hidden `
        -WorkingDirectory $Root

    $ready = $false
    for ($i = 0; $i -lt 120; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-Workbench) {
            $ready = $true
            break
        }
    }

    if (-not $ready) {
        $shell = New-Object -ComObject WScript.Shell
        $shell.Popup(
            "工作台启动失败，请查看日志：`n$LogFile",
            20,
            "任务管理工作台",
            16
        ) | Out-Null
        if (-not $NoBrowser -and (Test-Path $LogFile)) {
            Start-Process notepad.exe $LogFile
        }
        exit 1
    }
}

if (-not $NoBrowser) {
    Start-Process $Url
}

exit 0
