param(
    [string]$Python = "D:\Demo\Vision\apps\dws_batch_model_validator\build\DWSBatchModelValidator\.venv\Scripts\python.exe",
    [string]$ModelPath = "D:\Demo\Vision\weights\yolo26s-seg-wds-1024-best_int8_openvino_model",
    [string]$Version = "1.1.0"
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VisionRoot = Resolve-Path (Join-Path $ProjectRoot "..")
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BuildRoot = Join-Path $VisionRoot "build\DWSVisionCountService_$Timestamp"
$StageRoot = Join-Path $BuildRoot "dist"
$ReleaseRoot = Join-Path $VisionRoot "dist\DWSVisionCountService_$Version`_$Timestamp"
$InstallerRoot = Join-Path $VisionRoot "dist_installer"
$Spec = Join-Path $ProjectRoot "packaging\windows\dws_vision_count_service.spec"
$WindowsConfig = Join-Path $ProjectRoot "packaging\windows\config.yaml"
$ModelName = "yolo26s-seg-wds-1024-best_int8_openvino_model"
$AppIcon = Join-Path $ProjectRoot "app\assets\app_icon.ico"

function Invoke-Checked {
    param(
        [string]$Name,
        [scriptblock]$Command
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
        throw "signtool.exe not found."
    }
    return $candidates[0].FullName
}

function Get-CodeSigningCert {
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
        Where-Object {
            $_.Subject -eq "CN=CVDS Local Code Signing" -and
            $_.NotAfter -gt (Get-Date).AddMonths(1)
        } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
    if ($null -eq $cert) {
        throw "CVDS Local Code Signing certificate not found."
    }
    return $cert
}

function Sign-File {
    param([string]$Path)
    $signTool = Get-SignTool
    $cert = Get-CodeSigningCert
    Invoke-Checked "Code signing $Path" {
        & $signTool sign /fd SHA256 /sha1 $cert.Thumbprint $Path
    }
    $signature = Get-AuthenticodeSignature -FilePath $Path
    if ($signature.Status -ne "Valid") {
        throw "Invalid Authenticode signature: $Path ($($signature.Status))"
    }
}

if (-not (Test-Path $Python)) {
    throw "Python not found: $Python"
}
if (-not (Test-Path $ModelPath)) {
    throw "Model not found: $ModelPath"
}
if (-not (Test-Path $AppIcon)) {
    throw "Application icon not found: $AppIcon"
}

New-Item -ItemType Directory -Force -Path $BuildRoot, $StageRoot, $ReleaseRoot, $InstallerRoot | Out-Null

Invoke-Checked "Native TurboJPEG build" {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_turbojpeg_decoder.ps1")
}
Invoke-Checked "Tests" {
    & $Python -m pytest -q
}
Invoke-Checked "Ruff" {
    & $Python -m ruff check .
}

$env:DWS_SERVICE_PROJECT_ROOT = $ProjectRoot
$env:DWS_SERVICE_ICON = $AppIcon
Invoke-Checked "PyInstaller" {
    & $Python -m PyInstaller --noconfirm --clean $Spec --distpath $StageRoot --workpath (Join-Path $BuildRoot "pyinstaller")
}

$PackagedRoot = Join-Path $StageRoot "DWSVisionCountService"
if (-not (Test-Path (Join-Path $PackagedRoot "DWSVisionCountService.exe"))) {
    throw "Packaged executable not found."
}
Copy-Item -Path (Join-Path $PackagedRoot "*") -Destination $ReleaseRoot -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseRoot "config"), (Join-Path $ReleaseRoot "models\$ModelName") | Out-Null
$ReleaseConfig = Join-Path $ReleaseRoot "config\config.yaml"
Copy-Item -LiteralPath $WindowsConfig -Destination $ReleaseConfig -Force
$ConfigText = Get-Content -Raw -Encoding UTF8 $ReleaseConfig
$ConfigText = $ConfigText -replace '(?m)^  version: .+$', "  version: $Version"
Set-Content -Encoding UTF8 -Path $ReleaseConfig -Value $ConfigText
Copy-Item -Path (Join-Path $ModelPath "*") -Destination (Join-Path $ReleaseRoot "models\$ModelName") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "WINDOWS_USER_GUIDE.md") -Destination (Join-Path $ReleaseRoot "UserGuide.md") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "test_image.jpg") -Destination (Join-Path $ReleaseRoot "test_image.jpg") -Force
Copy-Item -LiteralPath $AppIcon -Destination (Join-Path $ReleaseRoot "app_icon.ico") -Force

$ExePath = Join-Path $ReleaseRoot "DWSVisionCountService.exe"
$NativeDll = Join-Path $ReleaseRoot "_internal\native\turbojpeg_decoder\bin\dws_turbojpeg_decoder.dll"
$TurboJpegDll = Join-Path $ReleaseRoot "_internal\native\turbojpeg_decoder\bin\turbojpeg.dll"
Sign-File $ExePath
Sign-File $NativeDll
Sign-File $TurboJpegDll

Invoke-Checked "Packaged diagnostics" {
    & $ExePath --diagnose
}

$Process = Start-Process -FilePath $ExePath -WorkingDirectory $ReleaseRoot -WindowStyle Hidden -PassThru
try {
    $Listening = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $client = [Net.Sockets.TcpClient]::new()
            $client.Connect("127.0.0.1", 9100)
            $client.Dispose()
            $Listening = $true
            break
        } catch {
            if ($Process.HasExited) {
                throw "Packaged application exited before TCP startup."
            }
        }
    }
    if (-not $Listening) {
        throw "TCP port 9100 did not start."
    }
    Invoke-Checked "Packaged TCP smoke test" {
        & $Python (Join-Path $ProjectRoot "scripts\tcp_client_demo.py") `
            --host 127.0.0.1 `
            --port 9100 `
            --image (Join-Path $ReleaseRoot "test_image.jpg") `
            --task_id RELEASE_SMOKE `
            --encoding jpg
    }
} finally {
    if (-not $Process.HasExited) {
        $Process.CloseMainWindow() | Out-Null
        if (-not $Process.WaitForExit(10000)) {
            Stop-Process -Id $Process.Id -Force
        }
    }
}

$InnoSetup = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $InnoSetup)) {
    throw "Inno Setup 6 not found."
}
$InstallerScript = Join-Path $ProjectRoot "packaging\windows\installer.iss"
Invoke-Checked "Installer build" {
    & $InnoSetup `
        "/DSourceDir=$ReleaseRoot" `
        "/DOutputDir=$InstallerRoot" `
        "/DMyAppVersion=$Version" `
        $InstallerScript
}
$InstallerPath = Join-Path $InstallerRoot "DWSVisionCountService_Setup_$Version.exe"
Sign-File $InstallerPath

Write-Host "RELEASE_DIR=$ReleaseRoot"
Write-Host "INSTALLER=$InstallerPath"
