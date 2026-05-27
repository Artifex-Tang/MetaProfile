"""
产业前沿技术扫描监测工具入口。

启动命令：
    uvicorn metaprofile.scan_monitor.main:app --host 0.0.0.0 --port 8101

对应课题任务书指标 4.2 的"产业前沿技术扫描监测"工具。
本工具是分析层，通过 REST 调用画像层（profile_tech / profile_org / profile_project）数据，
不直接读取底座存储。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from metaprofile.scan_monitor.api import routes_frontier, routes_alert
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("scan_monitor_starting", env=settings.env)
    yield


app = FastAPI(
    title="产业前沿技术扫描监测服务",
    description="基于五维信号融合（关键词突现/专利异动/引用聚类/投融资/政策）+ LLM Agent 验证 + RAG TRL 标注",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(
    routes_frontier.router, prefix=settings.api_prefix, tags=["frontier-tech"]
)
app.include_router(
    routes_alert.router, prefix=settings.api_prefix, tags=["alerts"]
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "scan_monitor"}
