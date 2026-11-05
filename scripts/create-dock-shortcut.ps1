$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Exe = Join-Path $Root "desktop\src-tauri\target\release\task-workbench-desktop.exe"
$Icon = Join-Path $Root "assets\app.ico"

if (-not (Test-Path $Exe)) {
    throw "Release build not found: $Exe`nRun: cd desktop/src-tauri; cargo build --release"
}

$desktop = [Environment]::GetFolderPath("Desktop")
$linkPath = Join-Path $desktop "任务管理工作台（侧边栏）.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($linkPath)
$shortcut.TargetPath = $Exe
$shortcut.WorkingDirectory = $Root
$shortcut.IconLocation = "$Icon,0"
$shortcut.Description = "任务管理工作台 - 窄栏侧边窗口"
$shortcut.WindowStyle = 1
$shortcut.Save()

Write-Host "Desktop shortcut created: $linkPath"
