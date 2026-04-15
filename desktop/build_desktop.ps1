$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    throw "Python was not found. Install Python or create .venv first."
}

$buildAssets = Join-Path $PSScriptRoot "build_assets"
$browserDir = Join-Path $buildAssets "ms-playwright"
$distDir = Join-Path $repoRoot "dist-desktop"
$buildDir = Join-Path $repoRoot "build-desktop"
$specFile = Join-Path $PSScriptRoot "uestc_tt_manager_desktop.spec"
$desktopRequirements = Join-Path $PSScriptRoot "requirements-desktop.txt"

New-Item -ItemType Directory -Force -Path $browserDir | Out-Null

& $python -m pip install -r (Join-Path $repoRoot "requirements.txt")
& $python -m pip install -r $desktopRequirements
& $python -m pip install pywebview==6.1 --no-deps

$env:PLAYWRIGHT_BROWSERS_PATH = $browserDir
& $python -m playwright install chromium

& $python -m PyInstaller --noconfirm --distpath $distDir --workpath $buildDir $specFile

Write-Host ""
Write-Host "Desktop build finished. Output directory: $distDir"
