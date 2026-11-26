<#
.SYNOPSIS
  停止 dev-start.ps1 起的后端与 Nginx。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\dev-stop.ps1
#>
param(
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "==> 停止 Nginx" -ForegroundColor Cyan
# nginx 是「一个 master + N 个 worker」，而且 master 有时会抢在杀进程之间重建 worker，
# 所以循环几轮，直到真的一个都不剩
$total = 0
for ($i = 0; $i -lt 5; $i++) {
    $nginx = Get-Process nginx -ErrorAction SilentlyContinue
    if (-not $nginx) { break }
    $total += $nginx.Count
    $nginx | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 400
}
if ($total -gt 0) {
    Write-Host "    已停止 $total 个 nginx 进程" -ForegroundColor Green
} else {
    Write-Host "    没有运行中的 nginx" -ForegroundColor Yellow
}

Write-Host "==> 停止后端（端口 $BackendPort）" -ForegroundColor Cyan
$stopped = 0
foreach ($c in Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue) {
    try {
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
        $stopped++
    } catch { }
}
$pidFile = Join-Path $Root ".tmp\backend.pid"
if (Test-Path $pidFile) {
    $savedPid = Get-Content $pidFile | Select-Object -First 1
    if ($savedPid) {
        try { Stop-Process -Id ([int]$savedPid) -Force -ErrorAction Stop; $stopped++ } catch { }
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}
Write-Host "    已停止 $stopped 个后端进程" -ForegroundColor Green

Start-Sleep -Milliseconds 500
foreach ($port in @($BackendPort, 8080)) {
    $left = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($left) {
        Write-Host "    端口 $port 仍被占用：$($left.OwningProcess -join ',')" -ForegroundColor Yellow
    } else {
        Write-Host "    端口 $port 已释放" -ForegroundColor Green
    }
}
