# CustLens 单容器镜像：nginx（前端 + 反代）+ uvicorn（后端）跑在同一个容器里
#
# 为什么需要它：deploy/Dockerfile.api + Dockerfile.web 是「两个容器」的生产形态，
# 适合自己的服务器 / docker compose。但 Render、Railway、Koyeb 这类平台一个服务只能跑
# 一个容器、一个端口，所以这里把前端与后端合到一个镜像，监听 $PORT。
#
# 构建：
#   docker build -f deploy/Dockerfile.app -t custlens:1.0.0 .
# 运行：
#   docker run --rm -p 8080:8080 custlens:1.0.0

# ---------- 阶段 1：构建前端 ----------
FROM node:20-alpine AS fe

WORKDIR /app
RUN npm install -g pnpm@10

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install

COPY frontend/ ./
RUN pnpm build

# ---------- 阶段 2：运行（nginx + uvicorn） ----------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    PORT=8080

RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx supervisor gettext-base curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/

COPY deploy/supervisord.conf /etc/supervisor/conf.d/custlens.conf
COPY deploy/nginx.allinone.conf.template /etc/nginx/templates/custlens.conf.template
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY --from=fe /app/dist frontend/dist

# 构建期生成数据：离线用仓库自带的原始 CSV，保证「镜像里的数据」和「代码版本」一致
WORKDIR /app/backend
RUN python /app/scripts/prepare_data.py

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
