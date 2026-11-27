#!/usr/bin/env bash
# CustLens 云服务器一键部署脚本（Ubuntu / Debian / CentOS / Rocky / Alma 通用）
#
# 用法（在服务器上执行，root 或 sudo）：
#   curl -fsSL https://raw.githubusercontent.com/TheLiYY/customer-insight-agent/main/deploy/vps-install.sh | bash
#   或者：把本文件传到服务器，然后 bash vps-install.sh
#
# 做的事：装 Docker → 拉仓库 → 构建并起容器（api + nginx）→ 打印访问地址
# 端口：默认宿主机 8080（云厂商安全组需要放行 8080；想用 80 见文末说明）

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/TheLiYY/customer-insight-agent.git}"
APP_DIR="${APP_DIR:-/opt/custlens}"
HOST_PORT="${HOST_PORT:-8080}"

log() { printf '\n\033[36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '\n\033[31m[错误]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 执行（或 sudo bash $0）"

# ---------- 1. 装 Docker ----------
if command -v docker >/dev/null 2>&1; then
  log "已装 Docker：$(docker --version)"
else
  log "安装 Docker ..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y ca-certificates curl git
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y git
    dnf install -y dnf-plugins-core
    dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo || true
    dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  elif command -v yum >/dev/null 2>&1; then
    yum install -y git
    yum install -y yum-utils
    yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo || true
    yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  else
    die "没识别出包管理器，请手动装 Docker 后重跑本脚本"
  fi
  systemctl enable --now docker
fi

docker compose version >/dev/null 2>&1 || die "缺少 docker compose 插件，请先安装"

# ---------- 2. 拉代码 ----------
if [ -d "$APP_DIR/.git" ]; then
  log "更新代码：$APP_DIR"
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" reset --hard origin/main
else
  log "克隆代码到 $APP_DIR"
  rm -rf "$APP_DIR"
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi

# ---------- 3. 指定对外端口并启动 ----------
cd "$APP_DIR"
log "构建镜像（首次约 3-6 分钟：装前端依赖 + 后端依赖 + 生成数据）..."
HOST_PORT="$HOST_PORT" docker compose up -d --build

log "等待服务就绪 ..."
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/api/health" >/dev/null 2>&1; then
    log "服务已就绪"
    break
  fi
  [ "$i" -eq 60 ] && die "60 次探测都失败，看日志：cd $APP_DIR && docker compose logs --tail=80"
  sleep 5
done

IP="$(curl -fsS --max-time 5 https://api.ipify.org || echo '<服务器公网IP>')"
cat <<EOF

============================================================
 部署完成

 访问地址：http://${IP}:${HOST_PORT}
 接口文档：http://${IP}:${HOST_PORT}/docs

 常用命令：
   cd ${APP_DIR}
   docker compose ps
   docker compose logs -f --tail=100
   docker compose restart
   git pull && docker compose up -d --build     # 更新版本
   docker compose down                          # 停止

 注意：
   1) 云厂商「安全组 / 防火墙」要放行 ${HOST_PORT} 端口（默认 8080），否则外网打不开；
   2) 想直接用 80 端口：编辑 docker-compose.yml，把 ports 改成 "80:80"，再 docker compose up -d；
   3) 想上 HTTPS：前面挂一层 Nginx / Caddy 反代到 127.0.0.1:${HOST_PORT} 即可（证书用 Let's Encrypt）。
============================================================

EOF
