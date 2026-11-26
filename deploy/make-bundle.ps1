<#
.SYNOPSIS
    打包本项目为「换机器直接跑」的离线部署包。

.DESCRIPTION
    做四件事：
      1) docker compose build 构建 api / web 两个镜像
      2) docker save 把镜像导出成 images.tar（含基础镜像层）
      3) 拷贝 compose 文件与说明文档
      4) 打印目标机器的启动命令（可选压成 zip）

    目标机器只要有 Docker（不需要 Node、不需要 Python、不需要联网），
    执行 docker load + docker compose up -d 即可跑起来。

.EXAMPLE
    pwsh deploy\make-bundle.ps1
    pwsh deploy\make-bundle.ps1 -OutDir E:\u盘\customer-insight -Zip

.NOTES
    需要本机已安装 Docker Desktop / Docker Engine + compose 插件。
    本脚本以 UTF-8(BOM) 保存，Windows PowerShell 5.1 与 PowerShell 7 都能正确读取中文。
#>
[CmdletBinding()]
param(
    [string]$OutDir = (Join-Path $PSScriptRoot '..\dist-bundle'),
    [string]$Tag = '1.0.0',
    [switch]$SkipBuild,
    [switch]$Zip
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
$apiImg = "customer-insight-api:$Tag"
$webImg = "customer-insight-web:$Tag"

function Write-Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

# 0. 环境检查
Write-Step '检查 docker 环境'
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    throw '没有检测到 docker 命令。请先安装 Docker Desktop 并启动，再运行本脚本。'
}
$engine = (& docker version --format '{{.Server.Version}}' 2>$null)
if (-not $engine) {
    throw 'Docker 引擎未运行（docker version 拿不到 Server 版本）。请启动 Docker Desktop 后重试。'
}
Write-Host "Docker 引擎版本：$engine"

Push-Location $root
try {
    # 1. 构建镜像
    if ($SkipBuild) {
        Write-Step '跳过构建，直接打包现有镜像'
    } else {
        Write-Step "构建镜像（$apiImg / $webImg）"
        & docker compose build
        if ($LASTEXITCODE -ne 0) { throw "docker compose build 失败（退出码 $LASTEXITCODE）" }
    }

    # 2. 准备输出目录
    Write-Step "准备输出目录：$OutDir"
    if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
    New-Item -ItemType Directory -Path $OutDir | Out-Null

    # 3. 导出镜像
    Write-Step '导出镜像到 images.tar（几百 MB，请稍候）'
    & docker save -o (Join-Path $OutDir 'images.tar') $apiImg $webImg
    if ($LASTEXITCODE -ne 0) { throw "docker save 失败（退出码 $LASTEXITCODE）" }

    # 4. 拷贝 compose 与说明
    Copy-Item (Join-Path $PSScriptRoot 'docker-compose.bundle.yml') (Join-Path $OutDir 'docker-compose.yml')
    Copy-Item (Join-Path $PSScriptRoot 'DOCKER.md') (Join-Path $OutDir 'DOCKER.md')
    Copy-Item (Join-Path $PSScriptRoot 'BUNDLE_README.md') (Join-Path $OutDir 'README.md')
    $license = Join-Path $root 'LICENSE'
    if (Test-Path $license) { Copy-Item $license (Join-Path $OutDir 'LICENSE') }

    # 5. 汇总
    $tar = Get-Item (Join-Path $OutDir 'images.tar')
    Write-Step '完成'
    Write-Host ("包目录：{0}" -f $OutDir)
    Write-Host ("images.tar：{0:N1} MB" -f ($tar.Length / 1MB))
    Write-Host ''
    Write-Host '目标机器执行：' -ForegroundColor Green
    Write-Host '  docker load -i images.tar'
    Write-Host '  docker compose up -d'
    Write-Host '  浏览器打开 http://localhost:8080'

    if ($Zip) {
        Write-Step '压缩为 zip（大文件，耗时较长）'
        $zipPath = "$OutDir.zip"
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
        Compress-Archive -Path (Join-Path $OutDir '*') -DestinationPath $zipPath -CompressionLevel Fastest
        Write-Host ("已生成：{0}（{1:N1} MB）" -f $zipPath, ((Get-Item $zipPath).Length / 1MB))
    }
}
finally {
    Pop-Location
}
