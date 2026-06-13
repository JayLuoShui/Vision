param(
    [switch]$IncludeAI,
    [string]$PythonVersion = "3.12",
    [string]$TorchExtraIndexUrl = "https://download.pytorch.org/whl/cu128"
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$AppEntry = Join-Path $RootDir "apps\cvds_annotation_tool_v2_3.py"
$AppPackageRoot = Join-Path $RootDir "apps\cvds_annotation_tool_v2_3\cvds_annotation_tool"
$PackageName = "CVDS_Annotation_Tool_v2.3"
if ($IncludeAI) {
    $PackageName = "CVDS_Annotation_Tool_v2.3_AI"
}

$BuildDir = Join-Path $RootDir "build\$PackageName"
$DistRoot = Join-Path $RootDir "dist"
$DistDir = Join-Path $DistRoot $PackageName
$ZipPath = Join-Path $DistRoot "$PackageName.zip"
$VenvDir = Join-Path $BuildDir ".venv"
$StageDistRoot = Join-Path $BuildDir "dist_stage"
$StageDistDir = Join-Path $StageDistRoot $PackageName

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

function Get-ReleaseProcesses {
    if (-not (Test-Path -LiteralPath $DistDir)) {
        return @()
    }

    $releaseRoot = [System.IO.Path]::GetFullPath($DistDir).TrimEnd('\')
    $releaseRootEscaped = [Regex]::Escape($releaseRoot)
    return @(Get-CimInstance Win32_Process | Where-Object {
        $exePath = $_.ExecutablePath
        $cmdLine = $_.CommandLine
        ($exePath -and $exePath.StartsWith($releaseRoot, [System.StringComparison]::OrdinalIgnoreCase)) -or
        ($cmdLine -and ($cmdLine -match $releaseRootEscaped))
    })
}

function Assert-ReleaseDirUnlocked {
    $processes = @(Get-ReleaseProcesses)
    if ($processes.Count -eq 0) {
        return
    }

    $processList = ($processes | ForEach-Object { "PID $($_.ProcessId): $($_.Name)" }) -join "`n"
    throw "Release directory is locked. Close the running $PackageName.exe processes and build again.`n$processList"
}

function Remove-PathStrict {
    param(
        [Parameter(Mandatory = $true)][string[]]$Paths,
        [Parameter(Mandatory = $true)][string]$FailureHint
    )

    foreach ($Path in $Paths) {
        if (Test-Path -LiteralPath $Path) {
            try {
                Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            }
            catch {
                throw "Cannot clean path: $Path`nReason: $($_.Exception.Message)`n$FailureHint"
            }
        }
    }
}

Assert-ReleaseDirUnlocked
Remove-PathStrict -Paths @($BuildDir) -FailureHint "Close programs using this path and run the build script again."
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

Invoke-Native "Create venv" "py" @("-$PythonVersion", "-m", "venv", $VenvDir)
$Python = Join-Path $VenvDir "Scripts\python.exe"
Invoke-Native "Upgrade pip" $Python @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Native "Install base requirements" $Python @("-m", "pip", "install", "-r", (Join-Path $ScriptDir "requirements.txt"))
if ($IncludeAI) {
    Invoke-Native "Install CUDA torch requirements" $Python @("-m", "pip", "install", "torch", "torchvision", "--index-url", $TorchExtraIndexUrl)
    Invoke-Native "Install optional AI requirements" $Python @("-m", "pip", "install", "ultralytics")
}
Invoke-Native "Install build requirements" $Python @("-m", "pip", "install", "pyinstaller", "pytest")

Push-Location $RootDir
try {
    Invoke-Native "Compile check" $Python @("-m", "py_compile", $AppEntry, (Join-Path $AppPackageRoot "main.py"), (Join-Path $AppPackageRoot "legacy_v2_3.py"))
    Invoke-Native "Runtime diagnose" $Python @($AppEntry, "--diagnose")
    $env:QT_QPA_PLATFORM = "offscreen"
    Invoke-Native "QApplication smoke test" $Python @($AppEntry, "--qapplication-test")
    Invoke-Native "Window smoke test" $Python @($AppEntry, "--window-smoke-test")
    Invoke-Native "Run pytest" $Python @("-m", "pytest", ".\tests\test_runtime_paths.py", ".\tests\test_yolo_io.py", ".\tests\test_defect_io.py", ".\tests\test_history.py", ".\tests\test_dataset_quality.py", ".\tests\test_backup_service.py", ".\tests\test_dataset_export.py", ".\tests\test_annotation_tool_v23_structure.py", "-q")
    $env:CVDS_PROJECT_ROOT = $RootDir
    $env:CVDS_ANNOTATION_PACKAGE_NAME = $PackageName
    $env:CVDS_ANNOTATION_INCLUDE_AI = "0"
    if ($IncludeAI) {
        $env:CVDS_ANNOTATION_INCLUDE_AI = "1"
    }
    Invoke-Native "PyInstaller build" $Python @("-m", "PyInstaller", "--noconfirm", (Join-Path $ScriptDir "cvds_annotation_tool.spec"), "--distpath", $StageDistRoot, "--workpath", (Join-Path $BuildDir "pyinstaller"))
    Assert-ReleaseDirUnlocked
    Remove-PathStrict -Paths @($DistDir, $ZipPath) -FailureHint "Close old exe, Explorer preview windows, or antivirus scans, then run the build script again."
    New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null
    Move-Item -LiteralPath $StageDistDir -Destination $DistDir -Force
    Compress-Archive -Path (Join-Path $DistDir "*") -DestinationPath $ZipPath -Force
    Invoke-Native "Release diagnose" (Join-Path $DistDir "$PackageName.exe") @("--diagnose")
    $env:QT_QPA_PLATFORM = "offscreen"
    Invoke-Native "Release window smoke test" (Join-Path $DistDir "$PackageName.exe") @("--window-smoke-test")
}
finally {
    Remove-Item Env:\CVDS_PROJECT_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:\CVDS_ANNOTATION_PACKAGE_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:\CVDS_ANNOTATION_INCLUDE_AI -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "Release directory: $DistDir"
Write-Host "Zip package: $ZipPath"
