param(
    [string]$Version = "",
    [string]$QtDir = $env:QT_DIR,
    [string]$OpenCvDir = $env:OPENCV_DIR,
    [string]$OnnxRuntimeRoot = $env:ONNXRUNTIME_ROOT,
    [string]$InnoSetup = $env:INNO_SETUP
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$RootDir = Split-Path -Parent (Split-Path -Parent $ProjectDir)
$TestBuildDir = Join-Path $RootDir "build\DatasetAssistant"
$BuildDir = Join-Path $RootDir "build\DatasetAssistant_release"
$DistDir = Join-Path $RootDir "dist\DatasetAssistant"
$InstallerDir = Join-Path $RootDir "dist_installer"

function Import-VcVars {
    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    $vcvarsCandidates = @(@(
        "$programFilesX86\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    ) | Where-Object { Test-Path $_ })
    if ($vcvarsCandidates.Count -eq 0) { return }
    $tempCmd = [System.IO.Path]::GetTempFileName() + ".cmd"
    Set-Content -Encoding ASCII -Path $tempCmd -Value "@echo off`r`ncall `"$($vcvarsCandidates[0])`" >nul`r`nset`r`n"
    $dump = cmd /d /c "`"$tempCmd`""
    Remove-Item $tempCmd -Force -ErrorAction SilentlyContinue
    foreach ($line in $dump) {
        $pair = $line -split "=", 2
        if ($pair.Count -eq 2) {
            Set-Item -Path "Env:$($pair[0])" -Value $pair[1]
        }
    }
}

function Invoke-Checked {
    param(
        [scriptblock]$Command,
        [string]$Name
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Get-SignTool {
    $candidates = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "\\x64\\signtool.exe$" } |
        Sort-Object FullName -Descending
    if ($candidates.Count -eq 0) {
        throw "signtool.exe was not found. Please install Windows SDK signing tools."
    }
    return $candidates[0].FullName
}

function Get-LocalCodeSigningCert {
    $subject = "CN=CVDS Local Code Signing"
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
        Where-Object { $_.Subject -eq $subject -and $_.NotAfter -gt (Get-Date).AddMonths(1) } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
    if ($null -ne $cert) {
        return $cert
    }
    return New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $subject `
        -CertStoreLocation Cert:\CurrentUser\My `
        -KeyUsage DigitalSignature `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -HashAlgorithm SHA256 `
        -NotAfter (Get-Date).AddYears(5)
}

function Invoke-CodeSign {
    param(
        [string]$Path
    )
    if (-not (Test-Path $Path)) {
        throw "File to sign was not found: $Path"
    }
    $cert = Get-LocalCodeSigningCert
    $signTool = Get-SignTool
    & $signTool sign /fd SHA256 /sha1 $cert.Thumbprint $Path
    if ($LASTEXITCODE -ne 0) {
        throw "Code signing failed for $Path with exit code $LASTEXITCODE"
    }
}

function Invoke-DiagnoseSmokeTest {
    & (Join-Path $DistDir "DatasetAssistant.exe") --diagnose
    if ($LASTEXITCODE -ne 0) {
        throw "diagnose failed with exit code $LASTEXITCODE"
    }
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = (Get-Content -Encoding UTF8 (Join-Path $ProjectDir "VERSION.txt") -TotalCount 1).Trim()
}
if ([string]::IsNullOrWhiteSpace($QtDir)) { $QtDir = "C:\Qt\6.9.3\msvc2022_64" }
if ([string]::IsNullOrWhiteSpace($OpenCvDir)) { $OpenCvDir = "C:\tools\opencv\build" }
if ([string]::IsNullOrWhiteSpace($OnnxRuntimeRoot)) { $OnnxRuntimeRoot = "C:\tools\onnxruntime-win-x64-gpu-1.23.2" }

Remove-Item -Recurse -Force $BuildDir, $DistDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $TestBuildDir, $BuildDir, $DistDir, $InstallerDir | Out-Null

Import-VcVars
Remove-Item Env:CC, Env:CXX -ErrorAction SilentlyContinue
$cl = Get-Command cl.exe -ErrorAction SilentlyContinue
if ($null -eq $cl) {
    throw "MSVC cl.exe was not found. Please install Visual Studio 2022 Build Tools."
}

Invoke-Checked { cmake -S $ProjectDir -B $TestBuildDir -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_C_COMPILER="$($cl.Source)" -DCMAKE_CXX_COMPILER="$($cl.Source)" -DCMAKE_PREFIX_PATH="$QtDir;$OpenCvDir" -DOpenCV_DIR="$OpenCvDir" -DONNXRUNTIME_ROOT="$OnnxRuntimeRoot" -DDATASET_ASSISTANT_BUILD_TESTS=ON } "cmake configure tests"
Invoke-Checked { cmake --build $TestBuildDir --config RelWithDebInfo } "cmake build tests"
Invoke-Checked { ctest --test-dir $TestBuildDir --output-on-failure } "ctest"

Invoke-Checked { cmake -S $ProjectDir -B $BuildDir -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER="$($cl.Source)" -DCMAKE_CXX_COMPILER="$($cl.Source)" -DCMAKE_PREFIX_PATH="$QtDir;$OpenCvDir" -DOpenCV_DIR="$OpenCvDir" -DONNXRUNTIME_ROOT="$OnnxRuntimeRoot" -DDATASET_ASSISTANT_BUILD_TESTS=OFF } "cmake configure release"
Invoke-Checked { cmake --build $BuildDir --config Release } "cmake build"
Invoke-CodeSign (Join-Path $BuildDir "DatasetAssistant.exe")

Copy-Item (Join-Path $BuildDir "DatasetAssistant.exe") (Join-Path $DistDir "DatasetAssistant.exe") -Force
& (Join-Path $QtDir "bin\windeployqt.exe") --release --no-translations --compiler-runtime (Join-Path $DistDir "DatasetAssistant.exe")

Get-ChildItem -Path $OpenCvDir -Recurse -Filter "opencv_*.dll" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notmatch "d\.dll$" } |
    Copy-Item -Destination $DistDir -Force
if (Test-Path $OnnxRuntimeRoot) {
    Get-ChildItem -Path (Join-Path $OnnxRuntimeRoot "lib") -Filter "*.dll" -ErrorAction SilentlyContinue |
        Copy-Item -Destination $DistDir -Force
}

Copy-Item (Join-Path $ProjectDir "VERSION.txt") $DistDir -Force
Copy-Item (Join-Path $ProjectDir "README.md") $DistDir -Force
Copy-Item (Join-Path $ProjectDir "packaging\README_RELEASE.md") $DistDir -Force
Copy-Item (Join-Path $ProjectDir "docs") (Join-Path $DistDir "docs") -Recurse -Force

Invoke-CodeSign (Join-Path $DistDir "DatasetAssistant.exe")
Invoke-DiagnoseSmokeTest

$isccCandidates = @(@(
    $InnoSetup,
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path $_) })
if ($isccCandidates.Count -eq 0) { throw "ISCC.exe was not found." }
Invoke-Checked { & $isccCandidates[0] /DAppVersion=$Version /DSourceDir="$DistDir" /DOutputDir="$InstallerDir" (Join-Path $ScriptDir "make_installer.iss") } "Inno Setup"
Invoke-CodeSign (Join-Path $InstallerDir "DatasetAssistant_Setup_$Version.exe")
