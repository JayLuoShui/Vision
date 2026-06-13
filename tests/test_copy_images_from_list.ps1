$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "..\scripts\copy_images_from_list.ps1"
$launcherPath = Join-Path $PSScriptRoot "..\scripts\双击这里开始复制图片.bat"
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("vision-copy-images-" + [Guid]::NewGuid().ToString("N"))
$sourceA = Join-Path $testRoot "source-a"
$sourceB = Join-Path $testRoot "source-b"
$destination = Join-Path $testRoot "destination"
$listPath = Join-Path $testRoot "list.txt"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Invoke-ExpectedFailure {
    param(
        [scriptblock]$Action,
        [string]$ExpectedText
    )

    try {
        & $Action
        throw "预期脚本失败，但实际成功。"
    }
    catch {
        Assert-True ($_.Exception.Message -like "*$ExpectedText*") "错误信息不包含：$ExpectedText"
    }
}

try {
    Assert-True (Test-Path -LiteralPath $launcherPath -PathType Leaf) "缺少可双击运行的 BAT 入口。"
    $launcherContent = [System.IO.File]::ReadAllText($launcherPath, [System.Text.Encoding]::UTF8)
    Assert-True (-not ($launcherContent.ToCharArray() | Where-Object { [int]$_ -gt 127 })) "BAT 入口必须使用纯 ASCII，避免 Windows CMD 解码失败。"
    Assert-True ($launcherContent -like "*copy_images_from_list.ps1*") "BAT 入口没有引用复制脚本。"
    Assert-True ($launcherContent -like "*powershell.exe*ExecutionPolicy Bypass*-File*") "BAT 入口没有通过 PowerShell 执行复制脚本。"

    New-Item -ItemType Directory -Path $sourceA, $sourceB | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $sourceA "第一张.jpg"), "image-a")
    [System.IO.File]::WriteAllText((Join-Path $sourceB "第二张.png"), "image-b")

    [System.IO.File]::WriteAllLines(
        $listPath,
        [string[]]@("", "第一张", "第二张.png"),
        [System.Text.UTF8Encoding]::new($false)
    )
    & $scriptPath -ListPath $listPath -SourcePaths @($sourceA, $sourceB) -DestinationPath $destination

    Assert-True (Test-Path -LiteralPath (Join-Path $destination "第一张.jpg")) "未复制不带后缀的名单文件。"
    Assert-True (Test-Path -LiteralPath (Join-Path $destination "第二张.png")) "未复制带后缀的名单文件。"

    [System.IO.File]::WriteAllLines(
        $listPath,
        [string[]]@("第一张", "第一张.jpg"),
        [System.Text.UTF8Encoding]::new($false)
    )
    Invoke-ExpectedFailure {
        & $scriptPath -ListPath $listPath -SourcePaths @($sourceA, $sourceB) -DestinationPath $destination
    } "名单中存在重复文件名"

    [System.IO.File]::WriteAllText($listPath, "不存在的图片", [System.Text.UTF8Encoding]::new($false))
    Invoke-ExpectedFailure {
        & $scriptPath -ListPath $listPath -SourcePaths @($sourceA, $sourceB) -DestinationPath $destination
    } "未找到图片"

    [System.IO.File]::WriteAllText((Join-Path $sourceB "第一张.jpeg"), "duplicate")
    [System.IO.File]::WriteAllText($listPath, "第一张", [System.Text.UTF8Encoding]::new($false))
    Invoke-ExpectedFailure {
        & $scriptPath -ListPath $listPath -SourcePaths @($sourceA, $sourceB) -DestinationPath $destination
    } "来源目录中存在同名图片"

    Write-Output "通过: 5，失败: 0"
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
