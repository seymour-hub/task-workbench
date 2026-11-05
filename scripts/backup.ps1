$ErrorActionPreference = "Stop"
try {
    $result = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8787/api/settings/backup"
    Write-Host "Backup created: $($result.path)"
} catch {
    Write-Host "Backend is not running. Start it first, then retry." -ForegroundColor Yellow
    exit 1
}
