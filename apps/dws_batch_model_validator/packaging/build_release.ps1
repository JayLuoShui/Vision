param(
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$BuildDir = Join-Path $RootDir "build\DWSBatchModelValidator"
$DistRoot = Join-Path $RootDir "dist"
$DistDir = Join-Path $DistRoot "DWSBatchModelValidator"
$ZipPath = Join-Path $DistRoot "DWSBatchModelValidator.zip"
$VenvDir = Join-Path $BuildDir ".venv"
$StageDistRoot = Join-Path $BuildDir "dist_stage"
$InstallerDir = Join-Path $RootDir "dist_installer"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )
    Write-Host "==> $Label"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Remove-PathStrict {
    param([string[]]$Paths)
    foreach ($Path in $Paths) {
        if (Test-Path -LiteralPath $Path) {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        }
    }
}

Remove-PathStrict @($BuildDir, $DistDir, $ZipPath)
New-Item -ItemType Directory -Force -Path $BuildDir, $DistRoot | Out-Null

Invoke-Native "Create venv" "py" @("-$PythonVersion", "-m", "venv", $VenvDir)
$Python = Join-Path $VenvDir "Scripts\python.exe"
Invoke-Native "Upgrade pip" $Python @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Native "Install core requirements" $Python @("-m", "pip", "install", "-r", (Join-Path $RootDir "requirements.txt"))
Invoke-Native "Install GUI requirements" $Python @("-m", "pip", "install", "-r", (Join-Path $RootDir "requirements-gui.txt"))
Invoke-Native "Install dev requirements" $Python @("-m", "pip", "install", "-r", (Join-Path $RootDir "requirements-dev.txt"))
Invoke-Native "Install project editable" $Python @("-m", "pip", "install", "-e", $RootDir)

Push-Location $RootDir
try {
    Invoke-Native "Run tests" $Python @("-m", "pytest", "tests", "-q")
    Invoke-Native "Run diagnose" $Python @("run_batch.py", "--diagnose")
    $env:QT_QPA_PLATFORM = "offscreen"
    Invoke-Native "GUI QApplication smoke test" $Python @("run_gui.py", "--qapplication-test")
    $env:DWS_VALIDATOR_PROJECT_ROOT = $RootDir
    Invoke-Native "PyInstaller build" $Python @("-m", "PyInstaller", "packaging\dws_batch_model_validator.spec", "--clean", "--noconfirm", "--distpath", $StageDistRoot, "--workpath", (Join-Path $BuildDir "pyinstaller"))
    Remove-PathStrict @($DistDir, $ZipPath)
    Move-Item -LiteralPath (Join-Path $StageDistRoot "DWSBatchModelValidator") -Destination $DistDir -Force
    if (-not (Test-Path -LiteralPath (Join-Path $DistDir "DWSBatchModelValidator.exe"))) {
        throw "DWSBatchModelValidator.exe was not generated."
    }
    Invoke-Native "Release diagnose" (Join-Path $DistDir "DWSBatchModelValidator.exe") @("--diagnose")
    $env:QT_QPA_PLATFORM = "offscreen"
    Invoke-Native "Release window smoke test" (Join-Path $DistDir "DWSBatchModelValidator.exe") @("--window-smoke-test")
    Compress-Archive -Path (Join-Path $DistDir "*") -DestinationPath $ZipPath -Force

    $isccCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if ($iscc) {
        New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null
        Invoke-Native "Build installer" $iscc @((Join-Path $ScriptDir "make_installer.iss"))
    } else {
        Write-Host "Inno Setup not found. Installer step skipped."
    }
}
finally {
    Remove-Item Env:\DWS_VALIDATOR_PROJECT_ROOT -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "Release directory: $DistDir"
Write-Host "Zip package: $ZipPath"
