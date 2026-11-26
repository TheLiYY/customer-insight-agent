"""Agent 对话接口。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.config import settings
from . import orchestrator, tools

agent_router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    history: list[dict[str, Any]] = Field(default_factory=list)


@agent_router.post("/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    return orchestrator.chat(req.message, req.history)


@agent_router.get("/suggestions")
def suggestions() -> dict[str, Any]:
    return {
        "suggestions": orchestrator.suggestions(),
        "tools": tools.public_specs(),
        "mode": "llm" if settings.llm_enabled else "rules",
        "model": settings.llm_model if settings.llm_enabled else "本地规则引擎",
    }
