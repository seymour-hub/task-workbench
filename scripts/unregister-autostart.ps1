$ErrorActionPreference = "Stop"
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $key -Name "TaskWorkbench" -ErrorAction SilentlyContinue
Write-Host "Autostart removed."
