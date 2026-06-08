param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..\..")
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"
$BuildDir = Join-Path $Root "build\CVDS_Jam_Video_Synthesizer"
$DistDir = Join-Path $Root "dist\CVDS_Jam_Video_Synthesizer"
$RuntimeDir = Join-Path $DistDir "runtime"

Set-Location $Root

if (Test-Path $BuildDir) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
}
if (Test-Path $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
}

if (-not (Test-Path $Python)) {
    python -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Pip install -r (Join-Path $Root "requirements.txt")

if (-not $SkipTests) {
    & $Python -m pytest (Join-Path $Root "tests\test_cvds_jam_video_synthesizer.py")
    & $Python -m compileall (Join-Path $Root "apps\cvds_jam_video_synthesizer")
}

& $PyInstaller --noconfirm (Join-Path $Root "CVDS_Jam_Video_Synthesizer.spec") --workpath $BuildDir --distpath (Join-Path $Root "dist")

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
$FfmpegSource = Join-Path $Root "runtime\ffmpeg.exe"
if (Test-Path $FfmpegSource) {
    Copy-Item -LiteralPath $FfmpegSource -Destination (Join-Path $RuntimeDir "ffmpeg.exe") -Force
}
if (Test-Path (Join-Path $Root "docs")) {
    Copy-Item -LiteralPath (Join-Path $Root "docs") -Destination (Join-Path $DistDir "docs") -Recurse -Force
}
if (Test-Path (Join-Path $Root "VERSION.txt")) {
    Copy-Item -LiteralPath (Join-Path $Root "VERSION.txt") -Destination (Join-Path $DistDir "VERSION.txt") -Force
}

Write-Host "Release output: $DistDir"
