$ErrorActionPreference = "Stop"

Write-Host "Installing Rust (rustup)..."
winget install --id Rustlang.Rustup -e --silent --accept-package-agreements --accept-source-agreements

Write-Host "Installing Visual Studio 2022 Build Tools (C++ workload)..."
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --silent --accept-package-agreements --accept-source-agreements --override "--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"

Write-Host "Tauri prerequisites installed. Restart the terminal before building."
