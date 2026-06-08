param(
    [string]$Version = "",
    [string]$QtDir = $env:QT_DIR,
    [string]$OpenCvDir = $env:OPENCV_DIR,
    [string]$InnoSetup = $env:INNO_SETUP,
    [string]$WorkerPythonExe = $env:CVDS_WORKER_PYTHON
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$AppSourceDir = Join-Path $RootDir "apps\cvds_cpp_detector"
$BuildDir = Join-Path $RootDir "build\cvds_cpp_detector_release"
$WorkerBuildDir = Join-Path $RootDir "build\cvds_worker"
$DistRoot = Join-Path $RootDir "dist\CVDS_Package_Flow_Detector"
$InstallerOut = Join-Path $RootDir "dist_installer"
$VersionFile = Join-Path $RootDir "VERSION.txt"

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = (Get-Content -Encoding UTF8 $VersionFile -TotalCount 1).Trim()
}

function Resolve-CommandPath([string]$Name, [string[]]$Candidates) {
    foreach ($candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    throw "$Name was not found. Please install it and retry."
}

function Import-VsDevEnvironment {
    if (Get-Command cl -ErrorAction SilentlyContinue) {
        return
    }
    $candidates = @(
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    )
    $vcvars = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($vcvars)) {
        throw "Visual Studio vcvars64.bat was not found."
    }
    $envLines = cmd /d /c "`"$vcvars`" > nul && set"
    foreach ($line in $envLines) {
        $index = $line.IndexOf("=")
        if ($index -gt 0) {
            [Environment]::SetEnvironmentVariable($line.Substring(0, $index), $line.Substring($index + 1), "Process")
        }
    }
}

function Resolve-WorkerPython([string]$ExplicitPath) {
    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath) -and (Test-Path $ExplicitPath)) {
        return (Resolve-Path $ExplicitPath).Path
    }
    foreach ($version in @("3.12", "3.11", "3.10", "3")) {
        $candidate = (& py "-$version" -c "import sys; print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path $candidate.Trim())) {
            return $candidate.Trim()
        }
    }
    throw "No supported Python runtime was found for worker packaging."
}

function Copy-DirectoryIfExists([string]$Source, [string]$Target) {
    if (Test-Path $Source) {
        New-Item -ItemType Directory -Force -Path $Target | Out-Null
        Copy-Item -Path (Join-Path $Source "*") -Destination $Target -Recurse -Force
    }
}

function Copy-ScriptFiles([string]$Source, [string]$Target) {
    if (Test-Path $Source) {
        New-Item -ItemType Directory -Force -Path $Target | Out-Null
        foreach ($name in @("worker_entry.py", "inspect_model_metadata.py", "pt_video_flow_monitor.py")) {
            Copy-Item -Path (Join-Path $Source $name) -Destination $Target -Force
        }
    }
}

Remove-Item -Recurse -Force $BuildDir, $WorkerBuildDir, $DistRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $BuildDir, $WorkerBuildDir, $DistRoot, $InstallerOut | Out-Null

Import-VsDevEnvironment

$prefixParts = @()
if (-not [string]::IsNullOrWhiteSpace($QtDir)) { $prefixParts += $QtDir }
if (-not [string]::IsNullOrWhiteSpace($OpenCvDir)) { $prefixParts += $OpenCvDir }
$prefixArg = $prefixParts -join ";"

$cmakeArgs = @("-S", $AppSourceDir, "-B", $BuildDir, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release")
if (-not [string]::IsNullOrWhiteSpace($prefixArg)) {
    $cmakeArgs += "-DCMAKE_PREFIX_PATH=$prefixArg"
}
if (-not [string]::IsNullOrWhiteSpace($OpenCvDir)) {
    $cmakeArgs += "-DOpenCV_DIR=$OpenCvDir"
}
cmake @cmakeArgs
cmake --build $BuildDir --config Release

$GuiExe = Get-ChildItem -Path $BuildDir -Recurse -Filter "CVDS_Cpp_Detector.exe" | Select-Object -First 1
if ($null -eq $GuiExe) { throw "C++ GUI exe was not found." }
Copy-Item $GuiExe.FullName (Join-Path $DistRoot "CVDS_Cpp_Detector.exe") -Force

$windeployqt = Resolve-CommandPath "windeployqt" @(
    (Join-Path $QtDir "bin\windeployqt.exe")
)
& $windeployqt --release --no-translations --compiler-runtime (Join-Path $DistRoot "CVDS_Cpp_Detector.exe")

if (-not [string]::IsNullOrWhiteSpace($OpenCvDir) -and (Test-Path $OpenCvDir)) {
    Get-ChildItem -Path $OpenCvDir -Recurse -Filter "opencv_*.dll" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch "d\.dll$" } |
        Copy-Item -Destination $DistRoot -Force
    Get-ChildItem -Path $OpenCvDir -Recurse -Filter "opencv_videoio_ffmpeg*.dll" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch "d\.dll$" } |
        Copy-Item -Destination $DistRoot -Force
}

$WorkerVenv = Join-Path $WorkerBuildDir ".venv"
$WorkerPythonSource = Resolve-WorkerPython $WorkerPythonExe
& $WorkerPythonSource -m venv $WorkerVenv
$WorkerPython = Join-Path $WorkerVenv "Scripts\python.exe"
& $WorkerPython -m pip install --upgrade pip
& $WorkerPython -m pip install -r (Join-Path $ScriptDir "requirements-worker.txt")
& $WorkerPython -m PyInstaller `
    --clean `
    --onefile `
    --name cvds_detector_worker `
    --paths (Join-Path $AppSourceDir "scripts") `
    --hidden-import pt_video_flow_monitor `
    --hidden-import inspect_model_metadata `
    --collect-all ultralytics `
    --collect-all torch `
    --collect-all torchvision `
    --collect-all nvidia `
    --collect-all cv2 `
    --distpath (Join-Path $WorkerBuildDir "dist") `
    --workpath (Join-Path $WorkerBuildDir "pyinstaller") `
    (Join-Path $AppSourceDir "scripts\worker_entry.py")

New-Item -ItemType Directory -Force -Path (Join-Path $DistRoot "runtime") | Out-Null
Copy-Item (Join-Path $WorkerBuildDir "dist\cvds_detector_worker.exe") (Join-Path $DistRoot "runtime\cvds_detector_worker.exe") -Force

Copy-DirectoryIfExists (Join-Path $AppSourceDir "configs") (Join-Path $DistRoot "configs")
Copy-ScriptFiles (Join-Path $AppSourceDir "scripts") (Join-Path $DistRoot "scripts")
Copy-DirectoryIfExists (Join-Path $RootDir "weights") (Join-Path $DistRoot "weights")
Copy-DirectoryIfExists (Join-Path $RootDir "docs") (Join-Path $DistRoot "docs")
Copy-Item $VersionFile (Join-Path $DistRoot "VERSION.txt") -Force
Copy-Item (Join-Path $RootDir "README_RELEASE.md") (Join-Path $DistRoot "README_RELEASE.md") -Force
if (Test-Path (Join-Path $RootDir "LICENSE")) {
    Copy-Item (Join-Path $RootDir "LICENSE") (Join-Path $DistRoot "LICENSE") -Force
}

# smoke test: cvds_detector_worker.exe diagnose
& (Join-Path $DistRoot "runtime\cvds_detector_worker.exe") diagnose
$DefaultModel = Get-ChildItem -Path (Join-Path $DistRoot "weights") -Filter "*.pt" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $DefaultModel) {
    & (Join-Path $DistRoot "runtime\cvds_detector_worker.exe") inspect-model --model $DefaultModel.FullName
}

$RequiredFiles = @(
    "CVDS_Cpp_Detector.exe",
    "runtime\cvds_detector_worker.exe",
    "configs\bytetrack.yaml",
    "VERSION.txt"
)
foreach ($file in $RequiredFiles) {
    if (-not (Test-Path (Join-Path $DistRoot $file))) {
        throw "Release directory is missing required file: $file"
    }
}

$iscc = Resolve-CommandPath "iscc" @(
    $InnoSetup,
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)

$env:CVDS_DIST_DIR = $DistRoot
$env:CVDS_INSTALLER_OUT = $InstallerOut
& $iscc /DAppVersion=$Version /DSourceDir="$DistRoot" /DOutputDir="$InstallerOut" (Join-Path $ScriptDir "make_installer.iss")

Write-Host "Release directory: $DistRoot"
Write-Host "Installer directory: $InstallerOut"
