"""
产业新技术发现工具入口（弱信号识别）。

启动命令：
    uvicorn metaprofile.new_tech_discovery.main:app --host 0.0.0.0 --port 8102

对应课题任务书指标 4.2 的"产业新技术发现"工具，
重点是【弱信号识别】（课题创新点 2）。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from metaprofile.new_tech_discovery.api import routes_new_tech, routes_signals
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("new_tech_discovery_starting", env=settings.env)
    yield


app = FastAPI(
    title="产业新技术发现服务",
    description="基于弱信号识别（NLP 文本挖掘 + 异常检测 + 趋势识别 + 信号关联网络）的产业新技术发现",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(
    routes_new_tech.router, prefix=settings.api_prefix, tags=["new-tech"]
)
app.include_router(
    routes_signals.router, prefix=settings.api_prefix, tags=["weak-signals"]
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "new_tech_discovery"}
