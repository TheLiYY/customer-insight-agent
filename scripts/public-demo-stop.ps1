# 停掉公网演示：隧道 + 对外 nginx(8090)。后端(8000)保留，用 scripts\dev-stop.ps1 停。
param([int]$PublicPort = 8090)

$nginxPrefix = 'C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Packages\nginxinc.nginx_Microsoft.Winget.Source_8wekyb3d8bbwe\nginx-1.31.10'
$nginxExe = Join-Path $nginxPrefix 'nginx.exe'

$cf = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cf) {
    $cf | Stop-Process -Force
    Write-Host "已停止 cloudflared 隧道" -ForegroundColor Yellow
} else {
    Write-Host "隧道本来就没在跑" -ForegroundColor DarkGray
}

$pidFile = Join-Path $nginxPrefix 'logs\nginx-public.pid'
if (Test-Path $pidFile) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & $nginxExe -p $nginxPrefix -c 'conf/nginx.public.conf' -s quit 2>&1 | Out-Null
    $ErrorActionPreference = $old
    Start-Sleep -Seconds 1
    Write-Host "已通知 8090 的 nginx 退出" -ForegroundColor Yellow
}

$listen = Get-NetTCPConnection -LocalPort $PublicPort -State Listen -ErrorAction SilentlyContinue
if ($listen) { Write-Host "端口 $PublicPort 仍被占用：$($listen.OwningProcess)" -ForegroundColor Red }
else { Write-Host "端口 $PublicPort 已释放" -ForegroundColor Green }
