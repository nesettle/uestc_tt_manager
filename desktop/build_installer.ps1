$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $repoRoot "dist-desktop"
$issFile = Join-Path $PSScriptRoot "installer\uestc_tt_manager.iss"
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $candidatePaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidatePaths) {
        if (Test-Path $candidate) {
            $iscc = $candidate
            break
        }
    }
}

if (-not (Test-Path $distDir)) {
    throw "dist-desktop does not exist. Run desktop\\build_desktop.ps1 first."
}
if (-not $iscc) {
    throw "Inno Setup Compiler (ISCC.exe) was not found. Install Inno Setup first."
}

& $iscc "/DRepoRoot=$repoRoot" "/DDistRoot=$distDir" $issFile

Write-Host ""
Write-Host "Installer build finished."
