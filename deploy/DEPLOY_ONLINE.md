# 公网部署

本机默认地址为 `http://127.0.0.1:8080`，仅本机可访问。若需对外提供访问，有两种方式：

- **A. 立刻可用、不注册**：内网穿透（cloudflared 临时隧道）——已在本机验证可用，但关掉电脑就没了。
- **B. 长期在线、需要账号**：云平台跑 `deploy/Dockerfile.app` 单容器镜像（Render / Railway / Fly / 自己的服务器）。

---

## A. 临时隧道（cloudflared）

启动脚本会依次拉起后端、8090 端口对外 nginx 与隧道，并把公网地址写入 `.tmp\public-url.txt`：

```powershell
scripts\public-demo-start.ps1          # 启动并打印 https://xxx.trycloudflare.com
scripts\public-demo-start.ps1 -Restart # 地址失效或无响应时重新启动（地址会变化）
scripts\public-demo-stop.ps1           # 停掉隧道与 8090
```

默认**不要求口令**（basic auth 在 SPA 子资源上会反复弹框），改由 nginx 对 `/api/import/*` 限流（6 次/分钟、突发 3）＋ 上传上限 24MB 兜底。要口令就把 `deploy/nginx.public.conf` 里 `auth_basic`/`auth_basic_user_file` 两行取消注释，并用 `openssl passwd -apr1 <密码> > deploy\.htpasswd` 生成（该文件不入库）。

手工步骤（脚本做了一样的事）：

```powershell
# 1) 起带口令的 nginx（监听 8090，口令文件 deploy\.htpasswd）
scripts\dev-start.ps1 -NoNginx            # 只确保后端在 8000
# 前置：logs\ 与 temp\{client_body_temp,proxy_temp,fastcgi_temp,uwsgi_temp,scgi_temp} 已存在
nginx.exe -p <nginx 前缀> -c D:\projects\customer-insight-agent\deploy\nginx.public.conf

# 2) 生成口令（首次）
openssl passwd -apr1 <你的密码> > deploy\.htpasswd   # 文件内容：demo:$apr1$xxxx$yyyy

# 3) 开隧道，日志里会打印 https://xxxx.trycloudflare.com
cloudflared.exe tunnel --url http://127.0.0.1:8090 --no-autoupdate --logfile .tmp\cf\tunnel.log
```

访问 `https://xxxx.trycloudflare.com/`，浏览器会弹一次账号密码框（`demo` / 你设的密码），之后同源资源都复用这份凭据。

注意：隧道 URL 每次重启都会变；电脑休眠就断；`deploy\.htpasswd` 里是真口令，**不要提交到仓库**（已在 `.gitignore`）。

---

## B. 云平台长期在线（Render，免费档）

镜像已经准备好：`deploy/Dockerfile.app`（nginx + uvicorn 同容器，监听 `$PORT`），蓝图文件 `render.yaml`。

1. 打开 https://render.com ，用 GitHub 登录（免费档不需要信用卡）。
2. **New → Blueprint**，选 `TheLiYY/customer-insight-agent`，Render 自动读 `render.yaml`。
3. 等构建（首次约 5–8 分钟：装前端依赖 + 后端依赖 + 构建期跑 `prepare_data.py`）。
4. 部署成功后会给你 `https://custlens.onrender.com`，打开即用。

其他平台同样使用 `deploy/Dockerfile.app`，仅需提供一个端口：

| 平台 | 操作要点 |
|---|---|
| Railway | New Project → Deploy from repo → 设置 Dockerfile 为 `deploy/Dockerfile.app` |
| Fly.io | `fly launch --dockerfile deploy/Dockerfile.app`，`internal_port = 8080` |
| 自己的服务器 | `docker build -f deploy/Dockerfile.app -t custlens . && docker run -d -p 80:8080 custlens`，前面再挂一层 HTTPS |

### 公网部署注意事项

1. **没有登录系统**：谁拿到地址谁就能上传数据。公开演示建议二选一：
   - 只放示例数据、限制上传（改 `backend/app/api/imports.py` 的 `MAX_BYTES` 或直接下线 `/api/import/apply`）；
   - 或者在外面套一层访问控制（Cloudflare Access、平台自带的密码保护、nginx `auth_basic`）。
2. **免费实例会休眠**：Render free 15 分钟无访问会休眠，第一次打开要等 30–60 秒唤醒，面试演示前先自己点一下预热。

---

## 本机验证记录

- 隧道：`https://penn-spoke-bomb-anna.trycloudflare.com` → 未带口令 401、带口令 `/` 200、`/api/health` 200、`/assets/*.js` 200（1.2MB）、`POST /api/import/inspect` 上传 1.7MB CSV 用时 10.2s 解析 8399 行成功。
- 单容器镜像：本机无 Docker，构建与运行由 CI 的 `docker` job 覆盖（`docker compose config` + 两个镜像构建 + 容器健康检查）。
