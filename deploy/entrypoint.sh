#!/bin/sh
# 单容器入口：把 $PORT 注入 nginx 配置，然后交给 supervisor 同时拉起 nginx 与 uvicorn
set -e

PORT="${PORT:-8080}"
mkdir -p /tmp/nginx/body /tmp/nginx/proxy

sed "s/__PORT__/${PORT}/g" /etc/nginx/templates/custlens.conf.template > /etc/nginx/conf.d/default.conf

# 去掉发行版自带的默认站点，避免抢 80 端口
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

echo "[entrypoint] nginx listen ${PORT}, api 127.0.0.1:8000"
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
