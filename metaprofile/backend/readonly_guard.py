"""只读模式熔断中间件。

settings.mode == "readonly" 时:
- 命中 BLOCKED_PREFIXES 的请求(ODS/采集/LLM/enrich/scheduler/db-connections)→ 503
- 画像层写语义(PUT/PATCH/DELETE 更新;POST /import /enrich)→ 503
POST /search /batch /semantic-search(读)与 GET 全保留。
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

# 画像层:PUT/PATCH/DELETE 全拦(更新/删除);POST 仅拦写语义(/import /enrich)
PROFILE_WRITE_METHODS = frozenset({"PUT", "PATCH", "DELETE"})
PROFILE_BLOCKED_POST_SEGMENTS = ("/import", "/enrich")

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
    if path.startswith("/api/v1/profile/"):
        if request.method in PROFILE_WRITE_METHODS:
            return _DISABLED_JSON
        if request.method == "POST" and any(
            seg in path for seg in PROFILE_BLOCKED_POST_SEGMENTS
        ):
            return _DISABLED_JSON

    return await call_next(request)
