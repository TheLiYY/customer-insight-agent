# 前端部署：Nginx（唯一方式）

本项目**前端只通过 Nginx 部署**：Nginx 托管 `frontend/dist` 里的静态文件，并把 `/api/` 反代到后端 FastAPI（`127.0.0.1:8000`）。
浏览器只访问 Nginx 一个地址，所以不需要 CORS，也不需要额外起任何静态服务器。

```
浏览器 ──► Nginx :8080 ──┬─► /                → frontend/dist/index.html（SPA 回落）
                         ├─► /assets/*.js|css → frontend/dist/assets（强缓存 1 年）
                         └─► /api/*           → 127.0.0.1:8000（FastAPI）
```

---

## 一、Windows（本机演示）

### 1. 先装 Nginx（已装过可跳过）

```powershell
winget install --id nginxinc.nginx -e --source winget
```

装好后重开终端，`nginx -v` 能出版本号即可（本机实测 `nginx/1.31.10`）。

### 2. 改配置里的两处路径

打开 [deploy/nginx.conf](nginx.conf)：

| 需要改的地方 | 默认值 | 说明 |
| --- | --- | --- |
| `root` | `D:/projects/customer-insight-agent/frontend/dist` | 你的 dist 绝对路径，Windows 也用正斜杠 |
| `listen` | `8080` | 端口被占用就换一个 |
| `upstream ... server` | `127.0.0.1:8000` | 后端地址 |

### 3. 建目录 + 检查 + 启动

Nginx 的日志和临时目录要预先存在（Windows 下不会自动递归创建）：

```powershell
cd D:\projects\customer-insight-agent\deploy
New-Item -ItemType Directory -Force logs, temp | Out-Null

nginx -p "D:/projects/customer-insight-agent/deploy" -c nginx.conf -t     # 检查配置，看到 syntax is ok 才行
nginx -p "D:/projects/customer-insight-agent/deploy" -c nginx.conf        # 启动
```

打开 <http://127.0.0.1:8080> 就是前端；后端要先跑起来（`python backend\run.py`）。

### 4. 常驻 / 停止 / 重载

```powershell
# 改完配置重载（不中断服务）
nginx -p "D:/projects/customer-insight-agent/deploy" -c nginx.conf -s reload

# 停止
nginx -p "D:/projects/customer-insight-agent/deploy" -c nginx.conf -s stop

# 想看错误日志
Get-Content D:\projects\customer-insight-agent\deploy\logs\error.log -Tail 20
```

> Nginx 在 Windows 上不像 Windows 服务那样自启，**开机后需要手动启动一次**。
> 想让它常驻，可以把上面的启动命令做成快捷方式/计划任务。

---

## 二、Linux（服务器部署）

```bash
# 1. 前端构建产物放好（本机构建后 rsync/scp 上去）
sudo mkdir -p /var/www/customer-insight/web
sudo rsync -av frontend/dist/ /var/www/customer-insight/web/

# 2. 配置
sudo cp deploy/nginx.conf /etc/nginx/conf.d/customer-insight.conf
#    把 root 改成 /var/www/customer-insight/web
#    把 listen 改成 80（或走已有 server 块）
sudo nginx -t && sudo systemctl reload nginx
```

后端用 systemd 托管（示例）：

```ini
# /etc/systemd/system/customer-insight-api.service
[Unit]
Description=Customer Insight Agent API
After=network.target

[Service]
WorkingDirectory=/opt/customer-insight/backend
ExecStart=/opt/customer-insight/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now customer-insight-api
```

> 生产环境建议再加 HTTPS（`certbot --nginx`），并把 Nginx 的 `root` 指向只读目录。

---

## 三、配置里做了什么（对应关系）

| 配置 | 作用 | 为什么这么写 |
| --- | --- | --- |
| `location /assets/` + `expires 1y, immutable` | 静态资源长缓存 | Vite 产物文件名带 hash，内容一变文件名就变，可以放心强缓存 |
| `location = /index.html` + `no-store` | 入口不缓存 | 发版后刷新立刻拿到新 bundle，不会白屏或加载旧代码 |
| `try_files $uri $uri/ /index.html` | SPA 路由回落 | 前端是单页应用，刷新 `/insights` 之类路径时仍要返回 index.html |
| `location /api/` + `proxy_pass http://upstream` | 接口反代 | 同源请求，前端不用配 CORS，也不暴露后端端口 |
| `location ~ ^/(docs|redoc|openapi\.json)$` | Swagger + OpenAPI | 浏览器直接看接口文档，Apifox 也能用 `http://<host>/openapi.json` 导入 |
| `gzip on` + `gzip_types ... text/javascript` | 压缩 | 前端 bundle 1.2MB → 约 405KB，首屏快很多 |
| `client_max_body_size 8m` | 上传体积 | 当前接口没有大文件，留余量防止 413 |
| `location = /healthz` | Nginx 自身探活 | 与后端 `/api/health` 区分，排障时先看 Nginx 活没活 |

---

## 四、排障对照表

| 现象 | 多半是 | 怎么查 |
| --- | --- | --- |
| 打开 8080 显示 Nginx 欢迎页 | 用了默认配置，没指定 `-c` | 启动命令必须带 `-p ... -c nginx.conf` |
| 页面空白、控制台 `/assets/xxx.js` 404 | `root` 指错了目录 | 确认 `root` 指向 `frontend/dist`，而不是 `frontend` |
| `/api/...` 返回 502 | 后端没起 / 端口不对 | `curl http://127.0.0.1:8000/api/health`，再看 `logs/error.log` 里的 `connect() failed` |
| 接口 404 但 Swagger 正常 | 少了 `location /api/` | 检查配置块是否被 include 进来、reload 是否成功 |
| 启动报 `CreateDirectory() ... temp\client_body_temp failed` | 没有 `temp` 目录 | `New-Item -ItemType Directory -Force logs, temp` 后重试 |
| 启动报 `bind() to 0.0.0.0:8080 failed (10048)` | 8080 被占用 | `Get-NetTCPConnection -LocalPort 8080` 找到进程，或换端口 |
| 改了配置没生效 | 没 reload | `nginx -p ... -c nginx.conf -s reload` |
