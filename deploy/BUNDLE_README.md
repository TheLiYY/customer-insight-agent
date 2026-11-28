# CustLens 离线部署包

这个文件夹拿到任何一台装了 Docker 的电脑上都能直接跑，不需要 Node、不需要 Python、
不需要联网下载依赖。

## 启动步骤

```bash
# 1. 导入镜像（只需一次）
docker load -i images.tar

# 2. 启动
docker compose up -d

# 3. 打开浏览器
#    http://localhost:8080
```

## 常用命令

```bash
docker compose ps                 # 看两个容器是否 healthy
docker compose logs -f web        # 前端日志（Nginx）
docker compose logs -f api        # 后端日志
docker compose down               # 停止并删除容器
docker compose up -d              # 再次启动
```

## 换端口

编辑 `docker-compose.yml` 里 web 服务的 `- "8080:80"`，例如改成 `- "18080:80"`，
然后 `docker compose up -d`，访问 http://localhost:18080 。

## 用自己的 Excel 数据

```bash
mkdir data
# 把 Excel 放进 data/ 文件夹，然后：
docker compose cp ./data/my_customers.xlsx api:/data/my_customers.xlsx
docker compose exec api python /app/scripts/prepare_data.py --xlsx /data/my_customers.xlsx
docker compose restart api
```

`prepare_data.py --xlsx` 会校验列名，缺字段会直接列出缺哪些列；处理完覆盖
`/app/backend/data/processed/customers.csv`，重启后所有页面与模型都基于新数据重算。

## 卸载镜像

```bash
docker rmi customer-insight-api:1.0.0 customer-insight-web:1.0.0
```

更细的说明（镜像结构图、构建原理、排障表）见 `DOCKER.md`。
