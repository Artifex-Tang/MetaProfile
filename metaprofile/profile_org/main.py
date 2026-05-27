"""
产业前沿科技机构画像工具入口。

启动命令：
    uvicorn metaprofile.profile_org.main:app --host 0.0.0.0 --port 8003

对应课题任务书指标 4.2 的"产业前沿科技机构画像"工具。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from metaprofile.profile_org.api import (
    routes_enrichment,
    routes_mutation,
    routes_query,
    routes_relation,
    routes_stats,
)
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("profile_org_starting", env=settings.env)
    yield
    logger.info("profile_org_stopping")


app = FastAPI(
    title="产业前沿科技机构画像服务",
    description=(
        "提供机构实体画像的查询/搜索/语义检索/批量查询/更新/导入/统计/"
        "关系查询/路径查询/变更查询/RAG补全 共 11 个标准 REST 接口。"
        "字段定义严格遵循《实体画像数据规范》机构节。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

PREFIX = settings.api_prefix
app.include_router(routes_query.router, prefix=PREFIX, tags=["query"])
app.include_router(routes_mutation.router, prefix=PREFIX, tags=["mutation"])
app.include_router(routes_relation.router, prefix=PREFIX, tags=["relation"])
app.include_router(routes_stats.router, prefix=PREFIX, tags=["stats"])
app.include_router(routes_enrichment.router, prefix=PREFIX, tags=["enrichment"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "profile_org"}
