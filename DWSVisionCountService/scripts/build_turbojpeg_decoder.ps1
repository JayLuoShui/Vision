param(
    [string]$LibJpegTurboRoot = $env:LIBJPEG_TURBO_ROOT
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SourceDir = Join-Path $ProjectRoot "native\turbojpeg_decoder"
$BuildDir = Join-Path $SourceDir "build"

if (-not $LibJpegTurboRoot -and $env:CONDA_PREFIX) {
    $CondaLibrary = Join-Path $env:CONDA_PREFIX "Library"
    if (Test-Path (Join-Path $CondaLibrary "include\turbojpeg.h")) {
        $LibJpegTurboRoot = $CondaLibrary
    }
}

if (-not $LibJpegTurboRoot) {
    $PackageRoot = Join-Path $env:USERPROFILE "miniconda3\pkgs"
    $Candidate = Get-ChildItem -Path $PackageRoot -Directory -Filter "libjpeg-turbo-*" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Where-Object { Test-Path (Join-Path $_.FullName "Library\include\turbojpeg.h") } |
        Select-Object -First 1
    if ($Candidate) {
        $LibJpegTurboRoot = Join-Path $Candidate.FullName "Library"
    }
}

if (-not $LibJpegTurboRoot) {
    throw "libjpeg-turbo not found. Set -LibJpegTurboRoot or LIBJPEG_TURBO_ROOT."
}

$VcVars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $VcVars)) {
    throw "Visual Studio 2022 C++ Build Tools not found."
}

$ConfigureCommand = 'call "{0}" && cmake -S "{1}" -B "{2}" -G Ninja -DCMAKE_BUILD_TYPE=Release -DLIBJPEG_TURBO_ROOT="{3}"' -f $VcVars, $SourceDir, $BuildDir, $LibJpegTurboRoot
$BuildCommand = 'call "{0}" && cmake --build "{1}" --config Release' -f $VcVars, $BuildDir

cmd.exe /d /s /c $ConfigureCommand
if ($LASTEXITCODE -ne 0) {
    throw "CMake configure failed with exit code $LASTEXITCODE"
}
cmd.exe /d /s /c $BuildCommand
if ($LASTEXITCODE -ne 0) {
    throw "C++ build failed with exit code $LASTEXITCODE"
}

Write-Host "Native decoder output: native\turbojpeg_decoder\bin"
