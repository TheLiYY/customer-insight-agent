# Docker 部署（换机器最省事的方式）

> 目标：把这套系统拷到另一台电脑上，**不装 Python、不装 Node、不装依赖**，
> 两条命令就能跑起来。所有环境都封在镜像里，启动后浏览器打开 `http://localhost:8080`。

---

## 一、为什么用 Docker

本地开发是「Anaconda venv + Node 构建 + Nginx」，换一台机器要重现这一堆东西很麻烦：
Python 版本、pandas/numpy/sklearn 版本、Node 版本、Nginx 配置路径……

Docker 把这些打包成一个**不可变的镜像**，目标机器只要有 Docker：

| 对比项 | 本地环境方式 | Docker 方式 |
| --- | --- | --- |
| 目标机需要装 | Python 3.13、pip 依赖、Node 20、Nginx、配置路径 | 只装 Docker |
| 首次部署耗时 | 30 分钟起，还可能踩版本坑 | 导入镜像 2 分钟，启动 10 秒 |
| 环境一致性 | 每台机器都可能不同 | 完全相同 |
| 卸载 | 逐个卸 | `docker compose down` + 删镜像 |

本机的开发方式（`.venv` + `deploy/nginx.conf`）依然保留，两者不冲突：

- **本机开发/改代码**：用 venv + 本地 Nginx（改完 `pnpm build` 立刻能看到）
- **换机演示/交付给别人**：用 Docker

---

## 二、镜像结构

```
浏览器
   │  http://localhost:8080
   ▼
┌─────────────────────────────────────────────┐
│ web 容器（nginx:stable-alpine，对外 8080→80）  │
│   /            → /usr/share/nginx/html      │  ← 前端 dist（构建阶段打进镜像）
│   /assets/*    → 强缓存 1 年 + gzip          │
│   /api/*       → 反代到 api:8000            │
└───────────────┬─────────────────────────────┘
                │ 容器内网 appnet（不发布到宿主机）
                ▼
┌─────────────────────────────────────────────┐
│ api 容器（python:3.13-slim）                 │
│   uvicorn app.main:app  → 0.0.0.0:8000      │
│   内置 2021 行清洗后数据 + sklearn/mlxtend   │
└─────────────────────────────────────────────┘
```

关键设计：

- **只有 web 对外发布端口**，api 只在容器内网可达 —— 后端不直接暴露到宿主机。
- 前端由 Nginx 同时做「静态托管 + API 反代」，浏览器只看到一个同源地址，**没有跨域问题**。
- 前端镜像采用**多阶段构建**：`node:20` 只用来打包，最终镜像里没有 Node，体积小、攻击面小。
- api 镜像在构建时用镜像内的原始 CSV 重新跑一次 `prepare_data.py`，保证**数据产物与代码版本一致**，构建过程不联网。
- `HEALTHCHECK` 让 compose 能判断 api 真起来了，再启动 web（`depends_on: service_healthy`）。

---

## 三、前置条件

| 系统 | 需要装的东西 |
| --- | --- |
| Windows 10/11 | [Docker Desktop](https://www.docker.com/products/docker-desktop/)，安装时会提示启用 **WSL2**（需要重启一次） |
| macOS | Docker Desktop |
| Linux | `docker` + `docker compose` 插件（Ubuntu：`sudo apt install docker.io docker-compose-plugin`） |

验证：

```bash
docker version          # 能看到 Server 段 = 引擎已启动
docker compose version  # 有输出 = compose 插件就绪
```

> Windows 上如果 `docker version` 报 `error during connect`，通常是 Docker Desktop 没启动，
> 或者 WSL2 没装好（`wsl --status` 会提示）。

---

## 四、一键启动（在项目根目录）

```bash
docker compose up -d --build
```

首次会拉取基础镜像并构建（联网，几分钟），之后启动只要几秒。检查状态：

```bash
docker compose ps
# 期望看到 api 为 healthy，web 为 running(healthy)
```

打开 **http://localhost:8080** 即可。

其他命令：

```bash
docker compose logs -f api     # 看后端日志
docker compose logs -f web     # 看 Nginx 日志
docker compose restart api     # 只重启后端
docker compose down            # 停止并删除容器（镜像保留）
docker compose down --rmi all  # 连镜像一起删
```

---

## 五、换机器部署（推荐：离线部署包）

### 5.1 打包

在**有 Docker 的源机器**上运行：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\make-bundle.ps1        # 构建 + 导出 + 组装部署包
powershell -ExecutionPolicy Bypass -File deploy\make-bundle.ps1 -Zip  # 额外压成 zip，方便拷 U 盘
```

产物在 `dist-bundle/`：

```
dist-bundle/
├── images.tar          # 两个镜像（含基础镜像层，几百 MB）
├── docker-compose.yml  # 无 build 段的 compose
├── DOCKER.md           # 本文件
└── README.md           # 目标机三步启动说明
```

### 5.2 目标机器

```bash
docker load -i images.tar     # 导入镜像
docker compose up -d          # 启动
# 浏览器：http://localhost:8080
```

**不需要联网、不需要源码、不需要装任何运行时。**

> 手动作业也可以：源机器 `docker save -o images.tar customer-insight-api:1.0.0 customer-insight-web:1.0.0`，
> 目标机器 `docker load -i images.tar`，再放一份 `deploy/docker-compose.bundle.yml` 改名为 `docker-compose.yml`。

---

## 六、换端口 / 换数据

### 换对外端口

编辑 `docker-compose.yml` 的 web 服务：

```yaml
    ports:
      - "18080:80"   # 从左到右：宿主机端口 : 容器端口（80 不要动）
```

`docker compose up -d` 生效。

### 换成自己的客户数据

数据是**自动识别列名**的（中英文都行），不需要先改成 iFood 那套表头：

```bash
mkdir data
copy 你的客户表.xlsx data\my_customers.xlsx          # 或 cp
docker compose cp ./data/my_customers.xlsx api:/data/my_customers.xlsx
docker compose exec api python /app/scripts/prepare_data.py --file /data/my_customers.xlsx
docker compose restart api
```

跑完会把 `backend/data/processed/customers.csv` 覆盖成新数据，重启后所有页面、模型、
结论都基于新数据重新计算。

- 少数列名认不出来时，去 `backend/app/core/schema.py` 的 `STANDARD_FIELDS` 里补别名；
  也可以先在下文「构建期重新生成数据」之前把文件放进 `backend/data/raw/`。
- 表里没有金额 / 没有响应标签也能跑：后端会输出能力开关（`capabilities`），前端自动隐藏算不出来的图。
  详细规则见仓库根目录的 [`docs/DATA.md`](../docs/DATA.md)。
- 也可以直接换成内置的另外两套数据验证降级效果：
  `docker compose exec api python /app/scripts/prepare_data.py --dataset mall`。

### 构建期重新生成数据（默认行为）

`deploy/Dockerfile.api` 里有一行 `RUN python /app/scripts/prepare_data.py`，
它在**构建时**用镜像内的原始 CSV 重新算一遍，保证「镜像里的数据」和「代码版本」永远一致，
不会出现代码改了、数据还是旧的。这一步不联网（走本地缓存）。

想换数据源，把 `Dockerfile.api` 那一行改成：

```dockerfile
RUN python /app/scripts/prepare_data.py --file /app/backend/data/raw/我的表.csv
```

> 想接在线大模型：取消 `docker-compose.yml` 里 `LLM_BASE_URL / LLM_API_KEY / LLM_MODEL` 的注释，
> 不配就是「离线规则模式」，功能完整可用。

---

## 七、排障

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `docker version` 连不上 | Docker Desktop 没启动 / WSL2 未装 | 启动 Docker Desktop；`wsl --status` 检查 |
| 构建卡在 `pip install` | 网络慢 | 换 pip 源（Dockerfile 里加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`） |
| 构建卡在 `pnpm install` | 网络慢 | 换 npm registry（`npm config set registry https://registry.npmmirror.com` 后再 build） |
| `port is already allocated` | 8080 被占用 | 改 compose 里的宿主端口 |
| `api` 一直 `unhealthy` | 数据或依赖加载失败 | `docker compose logs api` 看报错；容器内 `curl 127.0.0.1:8000/api/health` |
| 页面白屏、控制台 404 | 静态资源没进镜像 | 确认构建阶段 `pnpm build` 成功；`docker compose exec web ls /usr/share/nginx/html` |
| 前端能开但接口 502 | api 没起来 | `docker compose ps` 看 api 状态；`docker compose logs api` |
| 时间显示不对 | 容器时区 | compose 里已设 `TZ=Asia/Shanghai` |
| 改代码后页面没变 | 用了旧镜像 | `docker compose up -d --build` 重新构建 |

查看容器内细节：

```bash
docker compose exec api python -c "import pandas as pd; d=pd.read_csv('data/processed/customers.csv'); print(d.shape)"
docker compose exec web nginx -t
```

---

## 八、相关文件

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | 本地/服务器一键启动（含 build 段） |
| `deploy/Dockerfile.api` | 后端镜像：Python 3.13 + 依赖 + 内置数据 |
| `deploy/Dockerfile.web` | 前端镜像：node 构建 → nginx 托管 |
| `deploy/nginx.docker.conf` | 容器内站点配置（静态 + /api 反代 + SPA 回落） |
| `deploy/docker-compose.bundle.yml` | 换机器用的无 build 版 compose |
| `deploy/BUNDLE_README.md` | 部署包里给目标机器看的三步启动说明 |
| `deploy/make-bundle.ps1` | 一键打离线部署包（PowerShell 5.1 / 7 均可，文件以 UTF-8 BOM 保存） |
| `.dockerignore` | 排除 node_modules/.venv/.git 等，加快构建 |
---

## 九、本机验证状态（诚实说明）

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| compose 文件语法 | 已验证 | yaml.safe_load 解析 docker-compose.yml 与 deploy/docker-compose.bundle.yml 均通过 |
| 容器内 Nginx 配置 | 已验证 | 把 upstream api:8000 换成本机端口后，用本机 nginx 1.31.10 执行 
ginx -t 通过 |
| 打包脚本 | 已验证 | deploy/make-bundle.ps1 语法解析通过；「未装 Docker」的错误分支实测能给出中文提示 |
| 镜像实际构建 | ⚠️ 未在本机验证 | 本机没有安装 Docker Desktop / WSL2，docker build 无法执行 |
| 容器联调 | ⚠️ 未在本机验证 | 同上；推送到 GitHub 后 .github/workflows/ci.yml 的 docker 作业会真正构建、起容器并探活 |

> 也就是说：**配置文件与脚本形态已核对，镜像构建链路由 CI 首次验证**。
> 如果 CI 的 docker 作业报错，把 Actions 日志发我，按报错改 Dockerfile 即可。
