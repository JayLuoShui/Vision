$ErrorActionPreference = "Stop"
$ServiceName = "DWSVisionCountService"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Nssm = Get-Command nssm.exe -ErrorAction SilentlyContinue
if (-not $Nssm) {
  Write-Error "未找到 nssm.exe。请先安装 NSSM，并确保 nssm.exe 在 PATH 中。"
}
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
& $Nssm.Source install $ServiceName $Python "-m app.main --mode tcp --config config/config.yaml"
& $Nssm.Source set $ServiceName AppDirectory $Root
& $Nssm.Source set $ServiceName Start SERVICE_AUTO_START
Write-Host "已安装服务 $ServiceName"
