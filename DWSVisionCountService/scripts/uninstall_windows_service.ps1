$ErrorActionPreference = "Stop"
$ServiceName = "DWSVisionCountService"
$Nssm = Get-Command nssm.exe -ErrorAction SilentlyContinue
if (-not $Nssm) {
  Write-Error "未找到 nssm.exe。请先安装 NSSM，并确保 nssm.exe 在 PATH 中。"
}
& $Nssm.Source stop $ServiceName
& $Nssm.Source remove $ServiceName confirm
Write-Host "已卸载服务 $ServiceName"
