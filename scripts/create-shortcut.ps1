$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Icon = Join-Path $Root "assets\app.ico"
$Launcher = Join-Path $Root "scripts\launch.vbs"
$WScript = Join-Path $env:SystemRoot "System32\wscript.exe"

if (-not (Test-Path $Icon)) {
    Write-Host "Icon not found, generating..."
    & (Join-Path $PSScriptRoot "make-icon.ps1")
}

$desktop = [Environment]::GetFolderPath("Desktop")
$linkPath = Join-Path $desktop "任务管理工作台.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($linkPath)
$shortcut.TargetPath = $WScript
$shortcut.Arguments = "`"$Launcher`""
$shortcut.WorkingDirectory = $Root
$shortcut.IconLocation = "$Icon,0"
$shortcut.Description = "任务管理工作台 - 打开本地工作台"
$shortcut.WindowStyle = 7
$shortcut.Save()

Write-Host "Desktop shortcut created: $linkPath"
