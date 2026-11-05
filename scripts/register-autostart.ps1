$ErrorActionPreference = "Stop"
$server = Join-Path $PSScriptRoot "start-server.ps1"
$command = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$server`""
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $key -Name "TaskWorkbench" -Value $command
Write-Host "Autostart registered (HKCU Run: TaskWorkbench)."
