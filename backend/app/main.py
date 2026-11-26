"""FastAPI 应用入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent.routes import agent_router
from .api.routes import router
from .core.config import PROJECT_DIR, settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="客户画像 · 精准推送 · 个性化营销策略",
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


@app.get("/")
def root() -> dict:
    return {
        "app": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "api": "/api/overview",
        "agent": "/api/agent/chat",
    }


# 生产模式下直接托管前端构建产物（frontend/dist）
DIST = PROJECT_DIR / "frontend" / "dist"
if DIST.exists():
    app.mount("/app", StaticFiles(directory=str(DIST), html=True), name="frontend")
