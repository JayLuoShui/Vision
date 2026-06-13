[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$ListPath = "C:\Users\lenovo\Desktop\noread\新建 文本文档.txt",

    [string[]]$SourcePaths = @(
        "C:\Users\lenovo\Desktop\数据采集\DWS NanNing 20260502 #2",
        "C:\Users\lenovo\Desktop\数据采集\DWS NanNing 20260505 #2"
    ),

    [string]$DestinationPath = "C:\Users\lenovo\Desktop\noread"
)

$ErrorActionPreference = "Stop"
$imageExtensions = @(".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")
$utf8 = [System.Text.UTF8Encoding]::new($false, $true)

if (-not (Test-Path -LiteralPath $ListPath -PathType Leaf)) {
    throw "名单文件不存在：$ListPath"
}

foreach ($sourcePath in $SourcePaths) {
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) {
        throw "来源目录不存在：$sourcePath"
    }
}

$names = @(
    [System.IO.File]::ReadAllLines($ListPath, $utf8) |
        ForEach-Object { $_.Trim().Trim('"') } |
        Where-Object { $_ }
)

if ($names.Count -eq 0) {
    throw "名单文件没有有效文件名：$ListPath"
}

$requestedNames = @{}
$duplicateListNames = @()
foreach ($name in $names) {
    $leafName = [System.IO.Path]::GetFileName($name)
    $extension = [System.IO.Path]::GetExtension($leafName).ToLowerInvariant()
    $stem = if ($imageExtensions -contains $extension) {
        [System.IO.Path]::GetFileNameWithoutExtension($leafName)
    }
    else {
        $leafName
    }

    if ($requestedNames.ContainsKey($stem)) {
        $duplicateListNames += $name
        continue
    }

    $requestedNames[$stem] = $name
}

if ($duplicateListNames.Count -gt 0) {
    throw "名单中存在重复文件名：$($duplicateListNames -join '；')"
}

$filesByStem = @{}
foreach ($sourcePath in $SourcePaths) {
    foreach ($file in Get-ChildItem -LiteralPath $sourcePath -File -Recurse) {
        if ($imageExtensions -notcontains $file.Extension.ToLowerInvariant()) {
            continue
        }

        if (-not $filesByStem.ContainsKey($file.BaseName)) {
            $filesByStem[$file.BaseName] = @()
        }
        $filesByStem[$file.BaseName] += $file
    }
}

$missingNames = @()
$ambiguousNames = @()
$filesToCopy = @()
foreach ($stem in $requestedNames.Keys) {
    if (-not $filesByStem.ContainsKey($stem)) {
        $missingNames += $requestedNames[$stem]
        continue
    }

    $matches = @($filesByStem[$stem])
    if ($matches.Count -gt 1) {
        $ambiguousNames += $requestedNames[$stem]
        continue
    }

    $filesToCopy += $matches[0]
}

if ($missingNames.Count -gt 0) {
    throw "未找到图片：$($missingNames -join '；')"
}

if ($ambiguousNames.Count -gt 0) {
    throw "来源目录中存在同名图片：$($ambiguousNames -join '；')"
}

if (-not (Test-Path -LiteralPath $DestinationPath -PathType Container)) {
    New-Item -ItemType Directory -Path $DestinationPath | Out-Null
}

foreach ($file in $filesToCopy) {
    Copy-Item -LiteralPath $file.FullName -Destination $DestinationPath -Force
}

Write-Output "复制完成：$($filesToCopy.Count) 张图片"
Write-Output "目标目录：$DestinationPath"
