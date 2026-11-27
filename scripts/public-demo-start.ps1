# 启动公网演示：后端(8000) + 带限流的 nginx(8090) + cloudflared 隧道
#
# 用法：
#   scripts\public-demo-start.ps1              # 启动（已在跑就只打印地址）
#   scripts\public-demo-start.ps1 -Restart     # 强制重启隧道（地址会变）
#   scripts\public-demo-stop.ps1               # 停掉隧道与 8090
#
# 说明：隧道是 Cloudflare 的临时隧道（quick tunnel），本机不注册也能用。
#       地址写进 .tmp\public-url.txt；电脑关机/断网即失效。

param(
    [switch]$Restart,
    [int]$ApiPort = 8000,
    [int]$PublicPort = 8090
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path $root '.tmp'
$cf = Join-Path $tmp 'cf\cloudflared.exe'
$urlFile = Join-Path $tmp 'public-url.txt'
$logFile = Join-Path $tmp 'cf\tunnel.log'
New-Item -ItemType Directory -Force (Join-Path $tmp 'cf') | Out-Null

$nginxPrefix = 'C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Packages\nginxinc.nginx_Microsoft.Winget.Source_8wekyb3d8bbwe\nginx-1.31.10'
$nginxExe = Join-Path $nginxPrefix 'nginx.exe'

function Test-Http([string]$url) {
    try { return (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 8).StatusCode -eq 200 } catch { return $false }
}

# 1) 后端
if (-not (Test-Http "http://127.0.0.1:$ApiPort/api/health")) {
    Write-Host "[1/3] 启动后端 ..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot 'dev-start.ps1') -BackendPort $ApiPort -NoNginx
} else {
    Write-Host "[1/3] 后端已在 $ApiPort" -ForegroundColor DarkGray
}

# 2) 对外 nginx（8090）
if (-not (Test-Http "http://127.0.0.1:$PublicPort/healthz")) {
    Write-Host "[2/3] 启动对外 nginx（$PublicPort）..." -ForegroundColor Cyan
    foreach ($d in 'logs', 'temp\client_body_temp', 'temp\proxy_temp', 'temp\fastcgi_temp', 'temp\uwsgi_temp', 'temp\scgi_temp') {
        New-Item -ItemType Directory -Force (Join-Path $nginxPrefix $d) | Out-Null
    }
    Copy-Item (Join-Path $root 'deploy\nginx.public.conf') (Join-Path $nginxPrefix 'conf\nginx.public.conf') -Force
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & $nginxExe -p $nginxPrefix -c 'conf/nginx.public.conf' -t 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { $ErrorActionPreference = $old; throw 'nginx 配置校验失败，见 logs/error-public.log' }
    Start-Process $nginxExe -ArgumentList '-p', $nginxPrefix, '-c', 'conf/nginx.public.conf' -WindowStyle Hidden
    $ErrorActionPreference = $old
} else {
    Write-Host "[2/3] 对外 nginx 已在 $PublicPort" -ForegroundColor DarkGray
}

# 3) 隧道
$running = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($running -and -not $Restart) {
    $url = if (Test-Path $urlFile) { (Get-Content $urlFile -Raw).Trim() } else { '' }
    if ($url -and (Test-Http "$url/healthz")) {
        Write-Host "[3/3] 隧道已在运行：$url" -ForegroundColor Green
        return
    }
    Write-Host "[3/3] 隧道进程在但地址不通，重启 ..." -ForegroundColor Yellow
    $running | Stop-Process -Force
}
if ($Restart) { Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force }

if (-not (Test-Path $cf)) { throw "缺少 $cf，先下载 cloudflared（见 deploy/DEPLOY_ONLINE.md）" }

Write-Host "[3/3] 打开隧道 ..." -ForegroundColor Cyan
# 每次用新的日志文件，避免读到上一次留下的旧地址
$cfDir = Join-Path $tmp 'cf'
$logFile = Join-Path $cfDir ('tunnel-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
Start-Process $cf -ArgumentList 'tunnel', '--url', "http://127.0.0.1:$PublicPort", '--no-autoupdate', '--logfile', $logFile, '--loglevel', 'info' -WindowStyle Hidden

$url = ''
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 800
    if (Test-Path $logFile) {
        $m = Select-String -Path $logFile -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches |
             ForEach-Object { $_.Matches.Value } | Select-Object -First 1
        if ($m) { $url = $m; break }
    }
}
if (-not $url) { throw '没拿到隧道地址，看看 .tmp\cf\tunnel.log' }

$url | Set-Content -Path $urlFile -Encoding ascii
Write-Host ""
Write-Host "公网地址：$url" -ForegroundColor Green
Write-Host "（电脑关机/休眠即失效；要固定地址用 deploy\DEPLOY_ONLINE.md 里的 Render 方案）" -ForegroundColor DarkGray
