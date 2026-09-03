param(
    [string]$TesseractPath = "C:\Program Files\Tesseract-OCR"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# PowerShell 7.3+ can turn non-zero native exit codes into terminating errors
# before we have a chance to write the actual stderr into our log artifact.
# Keep native commands under explicit exit-code control instead.
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

# Force the checked-out repository to win over any similarly named package
# from site-packages and make pytest/module discovery deterministic.
$env:PYTHONPATH = $Root

$Logs = Join-Path $Root "logs"
$Release = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $Logs, $Release | Out-Null

$Transcript = Join-Path $Logs "build-windows.log"
Start-Transcript -Path $Transcript -Force | Out-Null

function Assert-LastExitCode {
    param(
        [string]$Step,
        [int]$Code
    )
    if ($Code -ne 0) {
        throw "$Step failed with exit code $Code"
    }
}

try {
    Write-Host "== Just InCard Windows Build =="
    python --version 2>&1 | Tee-Object -FilePath (Join-Path $Logs "python-version.txt")
    Assert-LastExitCode "python --version" $LASTEXITCODE

    python -c "import sys; assert sys.version_info[:2] == (3,11), 'Python 3.11 required'" 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "python-compatibility.txt")
    Assert-LastExitCode "Python compatibility check" $LASTEXITCODE

    Write-Host "== Validate repository =="
    python tools/validate_repository.py 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "repository-validation.txt")
    Assert-LastExitCode "Repository validation" $LASTEXITCODE

    Write-Host "== Materialize recovered Python 3.11 modules =="
    python tools/materialize_recovered_modules.py 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "materialize-recovered-modules.txt")
    Assert-LastExitCode "Recovery materialization" $LASTEXITCODE

    Write-Host "== Python package path diagnostics =="
    python -c "import sys, importlib.util, justincard; print('cwd=', __import__('os').getcwd()); print('sys.path=', sys.path); print('justincard=', getattr(justincard, '__file__', None), list(getattr(justincard, '__path__', []))); print('v108_core_spec=', importlib.util.find_spec('justincard.v108_core')); import justincard.v108_core; print('v108_core=', justincard.v108_core.__file__)" 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "python-import-path.txt")
    Assert-LastExitCode "Python package path diagnostics" $LASTEXITCODE

    Write-Host "== Source and search tests =="
    python -m pytest tests -vv 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "pytest.txt")
    Assert-LastExitCode "pytest" $LASTEXITCODE

    Write-Host "== Pre-build import diagnostics =="
    # Diagnostic only.  Older v1.0.5 stopped here before PyInstaller and the
    # PowerShell transcript swallowed the actual Python traceback.  The real
    # gate is the post-build EXE self-test below.
    python -m tools.smoke_imports --strict 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "prebuild-import-diagnostics.txt")
    $PreBuildImportExitCode = $LASTEXITCODE
    "Exit code: $PreBuildImportExitCode" |
        Add-Content -Encoding utf8 (Join-Path $Logs "prebuild-import-diagnostics.txt")
    if ($PreBuildImportExitCode -ne 0) {
        Write-Warning "Pre-build import diagnostics reported errors; continuing to PyInstaller for authoritative packaging diagnostics."
    }

    if (Test-Path $TesseractPath) {
        $env:TESSERACT_DIR = (Resolve-Path $TesseractPath).Path
        Write-Host "Bundling Tesseract from $env:TESSERACT_DIR"
    } else {
        Write-Warning "Tesseract directory not found: $TesseractPath"
        $env:TESSERACT_DIR = ""
    }

    Write-Host "== Clean previous packaging output =="
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
    Get-ChildItem $Release -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "== PyInstaller =="
    pyinstaller --noconfirm --clean JustInCard.spec 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "pyinstaller.txt")
    Assert-LastExitCode "PyInstaller" $LASTEXITCODE

    $BuiltExe = Join-Path $Root "dist\JustInCard\JustInCard.exe"
    if (-not (Test-Path $BuiltExe)) {
        throw "PyInstaller finished without creating $BuiltExe"
    }

    Write-Host "== Packaged EXE self-test =="
    $env:QT_QPA_PLATFORM = "offscreen"
    $SelfTestLog = Join-Path $Logs "postbuild-selftest.txt"
    Remove-Item -Force -ErrorAction SilentlyContinue $SelfTestLog
    $env:JIC_SELFTEST_LOG = $SelfTestLog
    try {
        & $BuiltExe --self-test
        $SelfTestExitCode = $LASTEXITCODE
    }
    finally {
        Remove-Item Env:JIC_SELFTEST_LOG -ErrorAction SilentlyContinue
    }
    if (Test-Path $SelfTestLog) {
        Get-Content $SelfTestLog | Write-Host
    } else {
        "The windowed EXE did not create the requested self-test log." |
            Set-Content -Encoding utf8 $SelfTestLog
    }
    Assert-LastExitCode "Packaged EXE self-test" $SelfTestExitCode

    Write-Host "== Packaged EXE UI startup self-test =="
    $UiSelfTestLog = Join-Path $Logs "postbuild-ui-selftest.txt"
    Remove-Item -Force -ErrorAction SilentlyContinue $UiSelfTestLog
    $env:JIC_SELFTEST_LOG = $UiSelfTestLog
    $env:QT_QPA_PLATFORM = "offscreen"
    try {
        & $BuiltExe --ui-self-test
        $UiSelfTestExitCode = $LASTEXITCODE
    }
    finally {
        Remove-Item Env:JIC_SELFTEST_LOG -ErrorAction SilentlyContinue
    }
    if (Test-Path $UiSelfTestLog) {
        Get-Content $UiSelfTestLog | Write-Host
    } else {
        "The windowed EXE did not create the requested UI self-test log." |
            Set-Content -Encoding utf8 $UiSelfTestLog
    }
    Assert-LastExitCode "Packaged EXE UI self-test" $UiSelfTestExitCode

    $VersionLine = python -c "from justincard.version import APP_VERSION; print(APP_VERSION)" 2>&1 |
        Tee-Object -FilePath (Join-Path $Logs "version-resolution.txt")
    Assert-LastExitCode "Version resolution" $LASTEXITCODE
    $Version = ($VersionLine | Select-Object -Last 1).Trim()
    if (-not $Version) {
        throw "Could not determine APP_VERSION"
    }

    $PortableName = "JustInCard-Windows-Portable-$Version"
    $PortableDir = Join-Path $Release $PortableName
    Copy-Item -Recurse -Force (Join-Path $Root "dist\JustInCard") $PortableDir
    New-Item -ItemType File -Force -Path (Join-Path $PortableDir "portable.flag") | Out-Null

    $VersionToken = $Version.Replace(".", "_")
    $Changelog = Join-Path $Root "CHANGELOG_v$VersionToken.txt"
    if (Test-Path $Changelog) {
        Copy-Item -Force $Changelog (Join-Path $PortableDir (Split-Path $Changelog -Leaf))
    }

    $ExePath = Join-Path $PortableDir "JustInCard.exe"
    $ExeHash = (Get-FileHash -Algorithm SHA256 $ExePath).Hash.ToLowerInvariant()
    "$ExeHash  JustInCard.exe" |
        Set-Content -Encoding ascii (Join-Path $PortableDir "JustInCard.exe.sha256")

    $ZipPath = Join-Path $Release "$PortableName.zip"
    Compress-Archive -Path "$PortableDir\*" -DestinationPath $ZipPath -CompressionLevel Optimal -Force
    $ZipHash = (Get-FileHash -Algorithm SHA256 $ZipPath).Hash.ToLowerInvariant()
    "$ZipHash  $PortableName.zip" | Set-Content -Encoding ascii "$ZipPath.sha256"

    @(
        "Just InCard Windows Build Summary"
        "Version: $Version"
        "Python: $(python --version 2>&1)"
        "Portable: $ZipPath"
        "Portable SHA256: $ZipHash"
        "EXE SHA256: $ExeHash"
        "Tesseract bundled: $([bool](Test-Path $TesseractPath))"
        "Pre-build import diagnostic exit code: $PreBuildImportExitCode"
        "Packaged EXE self-test exit code: $SelfTestExitCode"
        "Packaged EXE UI self-test exit code: $UiSelfTestExitCode"
    ) | Set-Content -Encoding utf8 (Join-Path $Logs "build-summary.txt")

    Write-Host "Portable build created: $ZipPath"
}
catch {
    $_ | Out-String | Set-Content -Encoding utf8 (Join-Path $Logs "build-exception.txt")
    Write-Error $_
    throw
}
finally {
    try {
        Stop-Transcript | Out-Null
    } catch {
        # Never hide the original build error because transcript shutdown failed.
    }
}
