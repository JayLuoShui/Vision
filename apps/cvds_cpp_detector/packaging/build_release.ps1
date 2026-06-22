param(
    [string]$Version = "",
    [string]$DistName = "CVDS_Package_Flow_Detector",
    [string]$QtDir = $env:QT_DIR,
    [string]$OpenCvDir = $env:OPENCV_DIR,
    [string]$InnoSetup = $env:INNO_SETUP,
    [string]$WorkerPythonExe = $env:CVDS_WORKER_PYTHON,
    [switch]$ReuseWorkerEnvironment,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppSourceDir = Split-Path -Parent $ScriptDir
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$BuildRoot = Join-Path $RootDir "build\$DistName"
$BuildDir = Join-Path $BuildRoot "cpp"
$WorkerBuildDir = Join-Path $BuildRoot "worker"
$DistRoot = Join-Path $RootDir "dist\$DistName"
$InstallerOut = Join-Path $RootDir "dist_installer"
$VersionFile = Join-Path $RootDir "VERSION.txt"

if ([string]::IsNullOrWhiteSpace($DistName)) {
    throw "DistName cannot be empty."
}
if ($DistName.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0) {
    throw "DistName contains invalid file name characters: $DistName"
}
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = (Get-Content -Encoding UTF8 $VersionFile -TotalCount 1).Trim()
}
if ([string]::IsNullOrWhiteSpace($Version)) {
    throw "Version cannot be empty."
}

function Invoke-Checked(
    [string]$Description,
    [string]$FilePath,
    [string[]]$Arguments = @()
) {
    & $FilePath @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Description failed with exit code $exitCode."
    }
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
    $envLines = Invoke-Checked "Visual Studio environment initialization" "cmd.exe" @(
        "/d",
        "/c",
        "`"$vcvars`" > nul && set"
    )
    foreach ($line in $envLines) {
        $index = $line.IndexOf("=")
        if ($index -gt 0) {
            [Environment]::SetEnvironmentVariable($line.Substring(0, $index), $line.Substring($index + 1), "Process")
        }
    }
}

function Resolve-WorkerPython([string]$ExplicitPath) {
    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "WorkerPythonExe was not found: $ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($null -eq $pyLauncher) {
        throw "No supported Python runtime was found for worker packaging."
    }
    foreach ($version in @("3.12", "3.11", "3.10", "3")) {
        $candidate = & $pyLauncher.Source "-$version" -c "import sys; print(sys.executable)" 2>$null
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate.Trim())) {
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

Remove-Item -Recurse -Force $BuildRoot, $DistRoot -ErrorAction SilentlyContinue
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
Invoke-Checked "CMake configure" "cmake" $cmakeArgs
Invoke-Checked "CMake build" "cmake" @("--build", $BuildDir, "--config", "Release")

$GuiExe = Get-ChildItem -Path $BuildDir -Recurse -Filter "CVDS_Cpp_Detector.exe" | Select-Object -First 1
if ($null -eq $GuiExe) { throw "C++ GUI exe was not found." }
Copy-Item $GuiExe.FullName (Join-Path $DistRoot "CVDS_Cpp_Detector.exe") -Force

$windeployqt = Resolve-CommandPath "windeployqt" @(
    (Join-Path $QtDir "bin\windeployqt.exe")
)
Invoke-Checked "Qt runtime deployment" $windeployqt @(
    "--release",
    "--no-translations",
    "--compiler-runtime",
    (Join-Path $DistRoot "CVDS_Cpp_Detector.exe")
)

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
$UseExistingWorkerEnvironment =
    -not [string]::IsNullOrWhiteSpace($WorkerPythonExe) -or $ReuseWorkerEnvironment
if ($UseExistingWorkerEnvironment) {
    $WorkerPython = $WorkerPythonSource
} else {
    Invoke-Checked "Worker virtual environment creation" $WorkerPythonSource @("-m", "venv", $WorkerVenv)
    $WorkerPython = Join-Path $WorkerVenv "Scripts\python.exe"
    Invoke-Checked "Worker pip upgrade" $WorkerPython @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Checked "Worker dependency installation" $WorkerPython @(
        "-m",
        "pip",
        "install",
        "-r",
        (Join-Path $ScriptDir "requirements-worker.txt")
    )
}

# PyInstaller 的 PyTorch 钩子会收集推理所需动态库，禁止整包收集以免带入开发和测试模块。
$PyInstallerArgs = @(
    "-m"
    "PyInstaller"
    "--clean"
    "--onedir"
    "--name"
    "cvds_detector_worker"
    "--paths"
    (Join-Path $AppSourceDir "scripts")
    "--hidden-import"
    "pt_video_flow_monitor"
    "--hidden-import"
    "inspect_model_metadata"
    "--collect-all"
    "ultralytics"
    "--collect-all"
    "cv2"
    "--collect-all"
    "onnxruntime"
    "--collect-all"
    "openvino"
    "--distpath"
    (Join-Path $WorkerBuildDir "dist")
    "--workpath"
    (Join-Path $WorkerBuildDir "pyinstaller")
    (Join-Path $AppSourceDir "scripts\worker_entry.py")
)
Invoke-Checked "Worker PyInstaller build" $WorkerPython $PyInstallerArgs

$WorkerOnedir = Join-Path $WorkerBuildDir "dist\cvds_detector_worker"
$RuntimeDir = Join-Path $DistRoot "runtime"
$WorkerExe = Join-Path $WorkerOnedir "cvds_detector_worker.exe"
if (-not (Test-Path -LiteralPath $WorkerExe -PathType Leaf)) {
    throw "PyInstaller onedir output is missing worker executable: $WorkerExe"
}
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
Copy-Item -Path (Join-Path $WorkerOnedir "*") -Destination $RuntimeDir -Recurse -Force

Copy-DirectoryIfExists (Join-Path $AppSourceDir "configs") (Join-Path $DistRoot "configs")
Copy-ScriptFiles (Join-Path $AppSourceDir "scripts") (Join-Path $DistRoot "scripts")
Copy-DirectoryIfExists (Join-Path $RootDir "weights") (Join-Path $DistRoot "weights")
Copy-DirectoryIfExists (Join-Path $AppSourceDir "docs") (Join-Path $DistRoot "docs")
Set-Content -Encoding UTF8 -LiteralPath (Join-Path $DistRoot "VERSION.txt") -Value $Version
Copy-Item (Join-Path $AppSourceDir "README_RELEASE.md") (Join-Path $DistRoot "README_RELEASE.md") -Force
if (Test-Path (Join-Path $RootDir "LICENSE")) {
    Copy-Item (Join-Path $RootDir "LICENSE") (Join-Path $DistRoot "LICENSE") -Force
}

# smoke test: cvds_detector_worker.exe diagnose
$PackagedWorker = Join-Path $DistRoot "runtime\cvds_detector_worker.exe"
Invoke-Checked "Packaged worker diagnose" $PackagedWorker @("diagnose")
$WeightsRoot = Join-Path $DistRoot "weights"
$SmokeModels = @(
    Get-ChildItem -Path $WeightsRoot -Filter "*.pt" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    Get-ChildItem -Path $WeightsRoot -Filter "*.onnx" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    Get-ChildItem -Path $WeightsRoot -Filter "*_openvino_model" -Directory -ErrorAction SilentlyContinue |
        Select-Object -First 1
) | Where-Object { $null -ne $_ }
foreach ($model in $SmokeModels) {
    Invoke-Checked "Packaged worker model inspection" $PackagedWorker @(
        "inspect-model",
        "--model",
        $model.FullName
    )
}

$RequiredFiles = @(
    "CVDS_Cpp_Detector.exe",
    "runtime\cvds_detector_worker.exe",
    "configs\bytetrack.yaml",
    "configs\regions.example.json",
    "VERSION.txt"
)
foreach ($file in $RequiredFiles) {
    if (-not (Test-Path (Join-Path $DistRoot $file))) {
        throw "Release directory is missing required file: $file"
    }
}

if (-not $SkipInstaller) {
    $iscc = Resolve-CommandPath "iscc" @(
        $InnoSetup,
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )
    Invoke-Checked "Inno Setup build" $iscc @(
        "/DAppVersion=$Version",
        "/DDistName=$DistName",
        "/DOutputBaseName=${DistName}_Setup_${Version}",
        "/DSourceDir=$DistRoot",
        "/DOutputDir=$InstallerOut",
        (Join-Path $ScriptDir "make_installer.iss")
    )
}

Write-Host "Release directory: $DistRoot"
if ($SkipInstaller) {
    Write-Host "Installer build skipped."
} else {
    Write-Host "Installer directory: $InstallerOut"
}
