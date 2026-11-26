<#
.SYNOPSIS
  一键启动：后端 API（127.0.0.1:8000）+ Nginx 静态站点（http://127.0.0.1:8080）。

.DESCRIPTION
  平时要开两个窗口、还要记得先杀掉旧 nginx 进程，很容易踩坑。
  这个脚本把「检查数据 → 清端口 → 起后端 → 等健康检查 → 起 nginx → 探活」串起来。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\dev-start.ps1
  powershell -ExecutionPolicy Bypass -File scripts\dev-start.ps1 -NoNginx
  powershell -ExecutionPolicy Bypass -File scripts\dev-start.ps1 -BackendPort 8010
#>
param(
    [int]$BackendPort = 8000,
    [switch]$NoNginx
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$WebUrl = "http://127.0.0.1:8080"

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Ok($text) { Write-Host "    $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "    $text" -ForegroundColor Yellow }

# ---------- 1. 找 python ----------
$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
    Write-Warn "没找到 .venv，改用系统 PATH 里的 python（依赖可能不全）"
}

# ---------- 2. 检查数据 ----------
$customers = Join-Path $Root "backend\data\processed\customers.csv"
if (-not (Test-Path $customers)) {
    Write-Step "首次运行，先准备数据"
    & $python (Join-Path $Root "scripts\prepare_data.py")
    if ($LASTEXITCODE -ne 0) { throw "数据准备失败，请先看上面的报错" }
    Write-Ok "数据已生成"
}

# ---------- 3. 清掉占着端口的旧进程 ----------
Write-Step "清理 $BackendPort 端口上的旧进程"
$listeners = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
foreach ($c in $listeners) {
    try {
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
        Write-Ok "已停止 pid=$($c.OwningProcess)"
    } catch {
        Write-Warn "无法停止 pid=$($c.OwningProcess)（$($_.Exception.Message)）"
    }
}
Start-Sleep -Milliseconds 500

# ---------- 4. 起后端 ----------
Write-Step "启动后端 API（127.0.0.1:$BackendPort）"
$env:BACKEND_PORT = "$BackendPort"
$logDir = Join-Path $Root ".tmp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$backendLog = Join-Path $logDir "backend.log"
$proc = Start-Process -FilePath $python -ArgumentList @((Join-Path $Root "backend\run.py")) `
    -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $backendLog -RedirectStandardError (Join-Path $logDir "backend.err.log")
$proc.Id | Out-File -Encoding ascii (Join-Path $logDir "backend.pid")

$healthy = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/health" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { }
    if ($proc.HasExited) { break }
}
if (-not $healthy) {
    Write-Warn "后端没有起来，日志：$backendLog"
    Get-Content $backendLog -Tail 20 -Encoding UTF8 -ErrorAction SilentlyContinue
    throw "后端启动失败（端口被占用或依赖缺失）"
}
Write-Ok "后端就绪：http://127.0.0.1:$BackendPort/api/health"

# ---------- 5. 起 nginx ----------
if ($NoNginx) {
    Write-Step "已跳过 nginx（-NoNginx）"
} else {
    Write-Step "启动 Nginx"
    $nginx = (Get-Command nginx.exe -ErrorAction SilentlyContinue).Source
    if (-not $nginx) {
        $candidates = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Directory -Filter "nginx*" -ErrorAction SilentlyContinue |
            ForEach-Object { Get-ChildItem $_.FullName -Directory -Filter "nginx-*" -ErrorAction SilentlyContinue } |
            ForEach-Object { Join-Path $_.FullName "nginx.exe" } |
            Where-Object { Test-Path $_ }
        $nginx = $candidates | Select-Object -First 1
    }

    if (-not $nginx) {
        Write-Warn "没找到 nginx.exe。安装：winget install -e --id nginxinc.nginx"
        Write-Warn "或者开发模式：cd frontend; pnpm dev（Vite 自带 /api 代理，端口 5173）"
    } else {
        $prefix = Split-Path -Parent $nginx
        # 旧进程必须清掉：残留的旧配置会继续占用 8080，看起来像「配置没生效」
        Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Milliseconds 500

        # nginx 在 Windows 上不会自己建临时目录，缺了会直接启动失败
        foreach ($d in @("logs", "temp\client_body_temp", "temp\proxy_temp", "temp\fastcgi_temp", "temp\uwsgi_temp", "temp\scgi_temp")) {
            New-Item -ItemType Directory -Force -Path (Join-Path $prefix $d) | Out-Null
        }

        $conf = Join-Path $Root "deploy\nginx.conf"
        # nginx -t 的提示走 stderr，在 ErrorActionPreference=Stop 下会被当成异常，这里临时放开
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $test = (& $nginx -p $prefix -c $conf -t 2>&1 | Out-String)
        $testCode = $LASTEXITCODE
        $ErrorActionPreference = $prevEap
        if ($testCode -ne 0) {
            Write-Warn $test.Trim()
            throw "nginx 配置检查失败（$conf）"
        }
        # 重定向输出，避免后台 nginx 继承当前控制台句柄（脚本会迟迟不退出）
        Start-Process -FilePath $nginx -ArgumentList @("-p", $prefix, "-c", $conf) -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDir "nginx.out.log") `
            -RedirectStandardError (Join-Path $logDir "nginx.err.log")
        Start-Sleep -Seconds 2

        try {
            $r = Invoke-WebRequest -Uri $WebUrl -UseBasicParsing -TimeoutSec 5
            Write-Ok "前端就绪：$WebUrl（$($r.StatusCode)）"
        } catch {
            Write-Warn "nginx 起来了但访问 $WebUrl 失败：$($_.Exception.Message)"
            Write-Warn "检查 frontend\dist 是否存在（没构建就 cd frontend; pnpm build）"
        }
    }
}

Write-Host ""
Write-Host "启动完成：" -ForegroundColor Green
Write-Host "  前端    $WebUrl"
Write-Host "  接口文档 http://127.0.0.1:$BackendPort/docs"
Write-Host "  健康检查 http://127.0.0.1:$BackendPort/api/health"
Write-Host "  停止服务 powershell -ExecutionPolicy Bypass -File scripts\dev-stop.ps1"
Write-Host "  后端日志 .tmp\backend.log"
