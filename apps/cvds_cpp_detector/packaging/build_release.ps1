param(
    [string]$Version = "",
    [string]$DistName = "CVDS_Cpp_Detector",
    [string]$QtDir = $env:QT_DIR,
    [string]$OpenCvDir = $env:OPENCV_DIR,
    [string]$OpenVinoDir = $env:OPENVINO_DIR,
    [string]$TensorRtDir = $env:TENSORRT_ROOT,
    [string]$InnoSetup = $env:INNO_SETUP,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$AppSourceDir = Join-Path $RootDir "apps\cvds_cpp_detector"
$BuildRoot = Join-Path $RootDir "build\$DistName"
$BuildDir = Join-Path $BuildRoot "cpp"
$DistRoot = Join-Path $RootDir "dist\$DistName"
$InstallerOut = Join-Path $RootDir "dist_installer"
$VersionFile = Join-Path $RootDir "VERSION.txt"
$ExeName = "CVDS_Cpp_Detector.exe"
$TargetName = "CVDS_Cpp_Detector"

if ([string]::IsNullOrWhiteSpace($DistName)) { throw "DistName 不能为空。" }
if ($DistName.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0) { throw "DistName 含有非法字符：$DistName" }
if (-not (Test-Path -LiteralPath $AppSourceDir -PathType Container)) { throw "找不到应用源码目录：$AppSourceDir" }
if ([string]::IsNullOrWhiteSpace($Version)) { $Version = (Get-Content -Encoding UTF8 $VersionFile -TotalCount 1).Trim() }
if ([string]::IsNullOrWhiteSpace($Version)) { throw "Version 不能为空。" }

function Invoke-Checked([string]$Description, [string]$FilePath, [string[]]$Arguments = @()) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Description 失败，退出码：$LASTEXITCODE" }
}

function Resolve-CommandPath([string]$Name, [string[]]$Candidates) {
    foreach ($candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }
    throw "找不到 $Name，请安装后重试。"
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
    $vcvars = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($vcvars)) { throw "找不到 Visual Studio vcvars64.bat。" }
    $envLines = & cmd.exe /d /c "`"$vcvars`" > nul && set"
    if ($LASTEXITCODE -ne 0) { throw "Visual Studio 环境初始化失败，退出码：$LASTEXITCODE" }
    foreach ($line in $envLines) {
        $index = $line.IndexOf("=")
        if ($index -gt 0) {
            [Environment]::SetEnvironmentVariable($line.Substring(0, $index), $line.Substring($index + 1), "Process")
        }
    }
}

function Copy-Dlls(
    [string[]]$Roots,
    [string[]]$Patterns,
    [string]$Target,
    [string]$AllowedNamePattern = ".*"
) {
    $copied = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($root in $Roots) {
        if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path -LiteralPath $root)) { continue }
        foreach ($pattern in $Patterns) {
            foreach ($file in Get-ChildItem -LiteralPath $root -Recurse -Filter $pattern -File -ErrorAction SilentlyContinue) {
                $isDebugDll = $file.Name -match "_debug\.dll$" -or $file.Name -match "^opencv.*d\.dll$" -or $file.Name -match "^Qt6.*d\.dll$"
                if ($isDebugDll -or $file.Name -notmatch $AllowedNamePattern -or -not $copied.Add($file.Name)) { continue }
                Copy-Item -LiteralPath $file.FullName -Destination $Target -Force
            }
        }
    }
    return $copied.Count
}

function Resolve-OpenCvRoots([string]$Hint) {
    if ([string]::IsNullOrWhiteSpace($Hint) -or -not (Test-Path -LiteralPath $Hint)) { return @() }
    $resolved = (Resolve-Path -LiteralPath $Hint).Path
    $roots = @(
        $resolved,
        (Join-Path $resolved "bin"),
        (Join-Path $resolved "x64\vc16\bin"),
        (Join-Path $resolved "x64\vc17\bin"),
        (Join-Path $resolved "..\bin"),
        (Join-Path $resolved "..\..\bin")
    )
    return $roots |
        Where-Object { Test-Path -LiteralPath $_ } |
        ForEach-Object { (Resolve-Path -LiteralPath $_).Path } |
        Select-Object -Unique
}

function Resolve-OpenVinoRoots([string]$Hint) {
    $roots = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in @($Hint, $env:INTEL_OPENVINO_DIR)) {
        if ([string]::IsNullOrWhiteSpace($candidate) -or -not (Test-Path -LiteralPath $candidate)) { continue }
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        $roots.Add($resolved)
        $roots.Add((Join-Path $resolved "libs"))
        $roots.Add((Join-Path $resolved "bin"))
        if ($resolved.EndsWith("runtime\cmake", [StringComparison]::OrdinalIgnoreCase)) {
            $runtimeRoot = Split-Path -Parent (Split-Path -Parent $resolved)
            $roots.Add($runtimeRoot)
            $roots.Add((Join-Path $runtimeRoot "bin\intel64\Release"))
            $roots.Add((Join-Path $runtimeRoot "3rdparty\tbb\bin"))
        } elseif ($resolved.EndsWith("\cmake", [StringComparison]::OrdinalIgnoreCase)) {
            $packageRoot = Split-Path -Parent $resolved
            $roots.Add($packageRoot)
            $roots.Add((Join-Path $packageRoot "libs"))
            $roots.Add((Join-Path $packageRoot "bin"))
        }
    }
    return $roots |
        Where-Object { Test-Path -LiteralPath $_ } |
        ForEach-Object { (Resolve-Path -LiteralPath $_).Path } |
        Select-Object -Unique
}

function Resolve-TensorRtRoots([string]$Hint) {
    $roots = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in @($Hint, $env:TENSORRT_ROOT, $env:TensorRT_ROOT, $env:TENSORRT_DIR, $env:NV_TENSORRT_ROOT)) {
        if ([string]::IsNullOrWhiteSpace($candidate) -or -not (Test-Path -LiteralPath $candidate)) { continue }
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        $roots.Add($resolved)
        $roots.Add((Join-Path $resolved "bin"))
        $roots.Add((Join-Path $resolved "lib"))
        $roots.Add((Join-Path $resolved "lib\x64"))
        $roots.Add((Join-Path $resolved "lib64"))
    }
    return $roots |
        Where-Object { Test-Path -LiteralPath $_ } |
        ForEach-Object { (Resolve-Path -LiteralPath $_).Path } |
        Select-Object -Unique
}

function Copy-OpenVinoModels([string]$SourceRoot, [string]$TargetRoot) {
    $modelFiles = Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -ErrorAction Stop |
        Where-Object { $_.Extension -in @(".xml", ".bin") }
    foreach ($file in $modelFiles) {
        $relativePath = $file.FullName.Substring($SourceRoot.Length).TrimStart("\")
        $targetPath = Join-Path $TargetRoot $relativePath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetPath) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $targetPath -Force
    }
    return @($modelFiles).Count
}

foreach ($path in @($BuildRoot, $DistRoot)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $path) { throw "无法清理旧目录：$path。请先关闭正在运行的软件后重试。" }
    }
}
New-Item -ItemType Directory -Force -Path $BuildDir, $DistRoot, $InstallerOut | Out-Null

Import-VsDevEnvironment

$prefixParts = @()
if (-not [string]::IsNullOrWhiteSpace($QtDir)) { $prefixParts += $QtDir }
if (-not [string]::IsNullOrWhiteSpace($OpenCvDir)) { $prefixParts += $OpenCvDir }
if (-not [string]::IsNullOrWhiteSpace($OpenVinoDir)) { $prefixParts += $OpenVinoDir }
if (-not [string]::IsNullOrWhiteSpace($TensorRtDir)) { $prefixParts += $TensorRtDir }

$cmakeArgs = @("-S", $AppSourceDir, "-B", $BuildDir, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release")
if ($prefixParts.Count -gt 0) { $cmakeArgs += "-DCMAKE_PREFIX_PATH=$($prefixParts -join ';')" }
if (-not [string]::IsNullOrWhiteSpace($OpenCvDir)) { $cmakeArgs += "-DOpenCV_DIR=$OpenCvDir" }
if (-not [string]::IsNullOrWhiteSpace($OpenVinoDir)) { $cmakeArgs += "-DOpenVINO_DIR=$OpenVinoDir" }
if (-not [string]::IsNullOrWhiteSpace($TensorRtDir)) { $cmakeArgs += "-DTENSORRT_ROOT=$TensorRtDir" }

Invoke-Checked "CMake 配置" "cmake" $cmakeArgs
Invoke-Checked "CMake 编译" "cmake" @("--build", $BuildDir, "--config", "Release", "--target", $TargetName)

$builtExe = Get-ChildItem -LiteralPath $BuildDir -Recurse -Filter $ExeName -File | Select-Object -First 1
if ($null -eq $builtExe) { throw "编译完成后找不到：$ExeName" }
$releaseExe = Join-Path $DistRoot $ExeName
Copy-Item -LiteralPath $builtExe.FullName -Destination $releaseExe -Force

$windeployqt = Resolve-CommandPath "windeployqt" @((Join-Path $QtDir "bin\windeployqt.exe"))
Invoke-Checked "Qt 运行库部署" $windeployqt @("--release", "--no-translations", "--compiler-runtime", $releaseExe)

$openCvRoots = @(Resolve-OpenCvRoots $OpenCvDir)
$openCvCount = Copy-Dlls $openCvRoots @("opencv*.dll", "opencv_videoio_ffmpeg*.dll") $DistRoot "^(?!opencv_java).*opencv.*\.dll$"
if ($openCvCount -eq 0) { throw "没有找到 OpenCV Release DLL，请正确设置 OPENCV_DIR。" }

$openVinoRoots = @(Resolve-OpenVinoRoots $OpenVinoDir)
$openVinoDllPattern = "^openvino(_c|_auto_batch_plugin|_auto_plugin|_hetero_plugin|_intel_cpu_plugin|_intel_gpu_plugin|_intel_npu_compiler|_intel_npu_compiler_loader|_intel_npu_plugin|_ir_frontend)?\.dll$"
$openVinoCount = Copy-Dlls $openVinoRoots @("openvino*.dll") $DistRoot $openVinoDllPattern
$openVinoIrFrontendCount = Copy-Dlls $openVinoRoots @("openvino_ir_frontend.dll") $DistRoot "^openvino_ir_frontend\.dll$"
$tbbCount = Copy-Dlls $openVinoRoots @("tbb*.dll") $DistRoot
if ($openVinoCount -eq 0) { throw "没有找到 OpenVINO Runtime DLL，请正确设置 OPENVINO_DIR。" }
if ($openVinoIrFrontendCount -eq 0) { throw "没有找到 openvino_ir_frontend.dll，OpenVINO 无法读取 .xml 模型。" }
if ($tbbCount -eq 0) { throw "没有找到 TBB DLL，请检查 OpenVINO Runtime 安装。" }

$tensorRtRoots = @(Resolve-TensorRtRoots $TensorRtDir)
if ($tensorRtRoots.Count -gt 0) {
    $tensorRtCount = Copy-Dlls $tensorRtRoots @("nvinfer*.dll", "nvonnxparser*.dll") $DistRoot
    if ($tensorRtCount -eq 0) { throw "已设置 TensorRT 路径，但没有找到 nvinfer*.dll。" }
}

$pluginsXml = $openVinoRoots |
    ForEach-Object { Get-ChildItem -LiteralPath $_ -Recurse -Filter "plugins.xml" -File -ErrorAction SilentlyContinue } |
    Select-Object -First 1
if ($null -ne $pluginsXml) { Copy-Item -LiteralPath $pluginsXml.FullName -Destination $DistRoot -Force }

$modelsDir = Join-Path $DistRoot "models"
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
$modelCount = Copy-OpenVinoModels (Join-Path $RootDir "weights") $modelsDir
if ($modelCount -eq 0) { throw "weights 中没有可发布的 OpenVINO IR .xml/.bin 文件。" }

Set-Content -Encoding UTF8 -LiteralPath (Join-Path $DistRoot "VERSION.txt") -Value $Version
Copy-Item -LiteralPath (Join-Path $AppSourceDir "README_RELEASE.md") -Destination (Join-Path $DistRoot "README_RELEASE.md") -Force
if (Test-Path -LiteralPath (Join-Path $RootDir "LICENSE")) {
    Copy-Item -LiteralPath (Join-Path $RootDir "LICENSE") -Destination (Join-Path $DistRoot "LICENSE") -Force
}

foreach ($required in @($ExeName, "VERSION.txt", "README_RELEASE.md")) {
    if (-not (Test-Path -LiteralPath (Join-Path $DistRoot $required))) { throw "发布目录缺少：$required" }
}

$blockedRuntimePattern = "^opencv_java.*\.dll$|" +
    "py" + "thon|" +
    "tor" + "ch|" +
    "ultra" + "lytics|" +
    "\.py$|\.pt$|\.onnx$|" +
    "work" + "er|" +
    "con" + "da"
$blockedRuntimeFiles = Get-ChildItem -LiteralPath $DistRoot -Recurse -File |
    Where-Object { $_.Name -match $blockedRuntimePattern }
if ($null -ne $blockedRuntimeFiles -and @($blockedRuntimeFiles).Count -gt 0) {
    $names = ($blockedRuntimeFiles | Select-Object -ExpandProperty Name -Unique) -join ", "
    throw "发布目录包含不允许的运行端文件：$names"
}

if (-not $SkipInstaller) {
    $iscc = Resolve-CommandPath "iscc" @(
        $InnoSetup,
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )
    Invoke-Checked "安装包生成" $iscc @(
        "/DAppVersion=$Version",
        "/DDistName=$DistName",
        "/DOutputBaseName=${DistName}_Setup_${Version}",
        "/DSourceDir=$DistRoot",
        "/DOutputDir=$InstallerOut",
        (Join-Path $ScriptDir "make_installer.iss")
    )
}

Write-Host "发布目录：$DistRoot"
if ($SkipInstaller) { Write-Host "已跳过安装包生成。" } else { Write-Host "安装包目录：$InstallerOut" }
