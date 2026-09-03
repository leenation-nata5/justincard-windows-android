$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
$Logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

try {
    $VersionOutput = python -c "from justincard.version import APP_VERSION; print(APP_VERSION)" 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "installer-version-resolution.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Version resolution failed with exit code $LASTEXITCODE"
    }
    $Version = ($VersionOutput | Select-Object -Last 1).Trim()

    $SourceDir = Join-Path $Root "release\JustInCard-Windows-Portable-$Version"
    if (-not (Test-Path $SourceDir)) {
        throw "Portable source directory missing: $SourceDir"
    }

    $Candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $ISCC = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $ISCC) {
        throw "Inno Setup 6 (ISCC.exe) was not found."
    }

    & $ISCC "/DAppVersion=$Version" "installer\JustInCard.iss" 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "inno-setup.log")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE"
    }

    $Setup = Join-Path $Root "release\JustInCard-Windows-Setup-$Version.exe"
    if (-not (Test-Path $Setup)) {
        throw "Installer output missing: $Setup"
    }

    $Hash = (Get-FileHash -Algorithm SHA256 $Setup).Hash.ToLowerInvariant()
    "$Hash  JustInCard-Windows-Setup-$Version.exe" |
        Set-Content -Encoding ascii "$Setup.sha256"
    Write-Host "Installer created: $Setup"
}
catch {
    $_ | Out-String |
        Set-Content -Encoding utf8 (Join-Path $Logs "installer-exception.txt")
    throw
}
