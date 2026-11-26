"""FastAPI 应用入口（纯 API 服务）。

前后端分离部署：这里只提供 /api 接口与 /docs 文档，
前端是一个独立的静态站点（开发时 Vite dev server，生产时任意静态服务器 / Nginx）。

好处：
1. 前端可以单独部署到 CDN，不占后端带宽；
2. 后端扩容、换语言都不影响前端；
3. 本地开发时前端 5173 通过代理访问 8000，跨域由 CORS 处理。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agent.routes import agent_router
from .api.routes import router
from .core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "客户画像 · 精准推送 · 个性化营销策略\n\n"
        "接口说明见仓库 docs/API.md；本服务的 /openapi.json 可直接导入 Apifox / Postman。"
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(agent_router)


@app.exception_handler(Exception)
async def unhandled_exception(request, exc: Exception) -> JSONResponse:
    """兜底：任何未捕获异常都返回结构化错误，方便前端提示。"""
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "app": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "api": "/api/overview",
        "agent": "/api/agent/chat",
        "note": "本项目前后端分离：前端由 Nginx 托管（deploy/nginx.conf），/api 反代到本服务。",
    }
