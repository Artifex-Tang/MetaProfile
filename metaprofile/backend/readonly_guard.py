"""只读模式熔断中间件。

settings.mode == "readonly" 时:
- 命中 BLOCKED_PREFIXES 的请求(ODS/采集/LLM/enrich/scheduler/db-connections)→ 503
- 画像层写方法(POST/PUT/PATCH/DELETE)→ 503
GET 画像查询 / 分析层(scan_monitor/new_tech/topic_selection)/ /health / /api/v1/runtime/flags 全保留。
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

# 整块熔断前缀(设置层 ODS/采集/LLM/enrich-tasks/scheduler/db-connections)
BLOCKED_PREFIXES: tuple[str, ...] = (
    "/api/v1/settings/datasources",
    "/api/v1/settings/collection",
    "/api/v1/settings/scheduled-tasks",
    "/api/v1/settings/enrichment-tasks",
    "/api/v1/settings/llm",
    "/api/v1/settings/db-connections",
    "/api/v1/settings/translate",  # scheduler translate/batch(走 LLM)
)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_DISABLED_JSON = JSONResponse(
    status_code=503,
    content={"detail": "disabled in readonly mode"},
)


async def readonly_guard(request: Request, call_next):
    mode = getattr(request.app.state, "mode", "full")
    if mode != "readonly":
        return await call_next(request)

    path = request.url.path
    if any(path.startswith(p) for p in BLOCKED_PREFIXES):
        return _DISABLED_JSON
    if request.method in WRITE_METHODS and path.startswith("/api/v1/profile/"):
        return _DISABLED_JSON

    return await call_next(request)
