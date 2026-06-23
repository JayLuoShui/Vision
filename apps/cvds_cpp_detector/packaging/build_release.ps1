param(
    [string]$Version = "",
    [string]$DistName = "CVDS_WCS_Multi_Camera_Monitor",
    [string]$QtDir = $env:QT_DIR,
    [string]$OpenCvDir = $env:OPENCV_DIR,
    [string]$OpenVinoDir = $env:OPENVINO_DIR,
    [string]$InnoSetup = $env:INNO_SETUP,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$AppSourceDir = Join-Path $RootDir "apps\CVDS_WCS_Multi_Camera_Monitor"
$BuildRoot = Join-Path $RootDir "build\$DistName"
$BuildDir = Join-Path $BuildRoot "cpp"
$DistRoot = Join-Path $RootDir "dist\$DistName"
$InstallerOut = Join-Path $RootDir "dist_installer"
$VersionFile = Join-Path $RootDir "VERSION.txt"
$ExeName = "CVDS_WCS_Multi_Camera_Monitor.exe"

if ([string]::IsNullOrWhiteSpace($DistName)) { throw "DistName cannot be empty." }
if ($DistName.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0) { throw "DistName contains invalid file name characters: $DistName" }
if (-not (Test-Path -LiteralPath $AppSourceDir -PathType Container)) { throw "Application source directory was not found: $AppSourceDir" }
if ([string]::IsNullOrWhiteSpace($Version)) { $Version = (Get-Content -Encoding UTF8 $VersionFile -TotalCount 1).Trim() }
if ([string]::IsNullOrWhiteSpace($Version)) { throw "Version cannot be empty." }

function Invoke-Checked([string]$Description, [string]$FilePath, [string[]]$Arguments = @()) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Description failed with exit code $LASTEXITCODE." }
}

function Resolve-CommandPath([string]$Name, [string[]]$Candidates) {
    foreach ($candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path $candidate)) { return (Resolve-Path $candidate).Path }
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }
    throw "$Name was not found. Please install it and retry."
}

function Import-VsDevEnvironment {
    if (Get-Command cl -ErrorAction SilentlyContinue) { return }
    $candidates = @(
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    )
    $vcvars = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($vcvars)) { throw "Visual Studio vcvars64.bat was not found." }
    $envLines = & cmd.exe /d /c "`"$vcvars`" > nul && set"
    if ($LASTEXITCODE -ne 0) { throw "Visual Studio environment initialization failed with exit code $LASTEXITCODE." }
    foreach ($line in $envLines) {
        $index = $line.IndexOf("=")
        if ($index -gt 0) { [Environment]::SetEnvironmentVariable($line.Substring(0, $index), $line.Substring($index + 1), "Process") }
    }
}

function Copy-DirectoryIfExists([string]$Source, [string]$Target) {
    if (Test-Path $Source) {
        New-Item -ItemType Directory -Force -Path $Target | Out-Null
        Copy-Item -Path (Join-Path $Source "*") -Destination $Target -Recurse -Force
    }
}

function Copy-Dlls([string]$Root, [string[]]$Patterns, [string]$Target) {
    if ([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path -LiteralPath $Root)) { return }
    foreach ($pattern in $Patterns) {
        Get-ChildItem -Path $Root -Recurse -Filter $pattern -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notmatch "d\.dll$" } |
            Copy-Item -Destination $Target -Force
    }
}

function OpenVinoRoots([string]$Hint) {
    $items = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in @($Hint, $env:INTEL_OPENVINO_DIR)) {
        if ([string]::IsNullOrWhiteSpace($candidate) -or -not (Test-Path -LiteralPath $candidate)) { continue }
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        $items.Add($resolved)
        if ($resolved.EndsWith("runtime\cmake", [StringComparison]::OrdinalIgnoreCase)) {
            $items.Add((Split-Path -Parent (Split-Path -Parent $resolved)))
        }
    }
    return $items | Select-Object -Unique
}

Remove-Item -Recurse -Force $BuildRoot, $DistRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $BuildDir, $DistRoot, $InstallerOut | Out-Null

Import-VsDevEnvironment

$prefixParts = @()
if (-not [string]::IsNullOrWhiteSpace($QtDir)) { $prefixParts += $QtDir }
if (-not [string]::IsNullOrWhiteSpace($OpenCvDir)) { $prefixParts += $OpenCvDir }
if (-not [string]::IsNullOrWhiteSpace($OpenVinoDir)) { $prefixParts += $OpenVinoDir }
$prefixArg = $prefixParts -join ";"

$cmakeArgs = @("-S", $AppSourceDir, "-B", $BuildDir, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release")
if (-not [string]::IsNullOrWhiteSpace($prefixArg)) { $cmakeArgs += "-DCMAKE_PREFIX_PATH=$prefixArg" }
if (-not [string]::IsNullOrWhiteSpace($OpenCvDir)) { $cmakeArgs += "-DOpenCV_DIR=$OpenCvDir" }
if (-not [string]::IsNullOrWhiteSpace($OpenVinoDir)) { $cmakeArgs += "-DOpenVINO_DIR=$OpenVinoDir" }
Invoke-Checked "CMake configure" "cmake" $cmakeArgs
Invoke-Checked "CMake build" "cmake" @("--build", $BuildDir, "--config", "Release", "--target", "CVDS_WCS_Multi_Camera_Monitor")

$GuiExe = Get-ChildItem -Path $BuildDir -Recurse -Filter $ExeName | Select-Object -First 1
if ($null -eq $GuiExe) { throw "Executable was not found: $ExeName" }
Copy-Item $GuiExe.FullName (Join-Path $DistRoot $ExeName) -Force

$windeployqt = Resolve-CommandPath "windeployqt" @((Join-Path $QtDir "bin\windeployqt.exe"))
Invoke-Checked "Qt runtime deployment" $windeployqt @("--release", "--no-translations", "--compiler-runtime", (Join-Path $DistRoot $ExeName))

Copy-Dlls $OpenCvDir @("opencv_*.dll", "opencv_videoio_ffmpeg*.dll") $DistRoot
foreach ($root in (OpenVinoRoots $OpenVinoDir)) {
    Copy-Dlls $root @("openvino*.dll", "tbb*.dll") $DistRoot
    Get-ChildItem -Path $root -Recurse -Filter "plugins.xml" -File -ErrorAction SilentlyContinue |
        Select-Object -First 1 |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $DistRoot -Force }
}

Copy-DirectoryIfExists (Join-Path $AppSourceDir "configs") (Join-Path $DistRoot "configs")
Copy-DirectoryIfExists (Join-Path $AppSourceDir "models") (Join-Path $DistRoot "models")
Copy-DirectoryIfExists (Join-Path $AppSourceDir "docs") (Join-Path $DistRoot "docs")
Set-Content -Encoding UTF8 -LiteralPath (Join-Path $DistRoot "VERSION.txt") -Value $Version
if (Test-Path (Join-Path $AppSourceDir "README_RELEASE.md")) {
    Copy-Item (Join-Path $AppSourceDir "README_RELEASE.md") (Join-Path $DistRoot "README_RELEASE.md") -Force
} elseif (Test-Path (Join-Path $AppSourceDir "README.md")) {
    Copy-Item (Join-Path $AppSourceDir "README.md") (Join-Path $DistRoot "README.md") -Force
}
if (Test-Path (Join-Path $RootDir "LICENSE")) { Copy-Item (Join-Path $RootDir "LICENSE") (Join-Path $DistRoot "LICENSE") -Force }

foreach ($file in @($ExeName, "configs\cameras.json", "configs\wcs.json", "configs\regions.json", "configs\runtime.json", "VERSION.txt")) {
    if (-not (Test-Path (Join-Path $DistRoot $file))) { throw "Release directory is missing required file: $file" }
}

if (-not $SkipInstaller) {
    $iscc = Resolve-CommandPath "iscc" @($InnoSetup, "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 6\ISCC.exe")
    Invoke-Checked "Inno Setup build" $iscc @("/DAppVersion=$Version", "/DDistName=$DistName", "/DOutputBaseName=${DistName}_Setup_${Version}", "/DSourceDir=$DistRoot", "/DOutputDir=$InstallerOut", (Join-Path $ScriptDir "make_installer.iss"))
}

Write-Host "Release directory: $DistRoot"
if ($SkipInstaller) { Write-Host "Installer build skipped." } else { Write-Host "Installer directory: $InstallerOut" }
