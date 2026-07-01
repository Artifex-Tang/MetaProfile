"""运行时标志端点:供前端读取当前模式以隐藏被熔断的菜单入口。"""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])


@router.get("/flags")
async def runtime_flags(request: Request) -> dict[str, str]:
    return {"mode": getattr(request.app.state, "mode", "full")}
