"""
产业科技动态选题工具入口。

启动命令：
    uvicorn metaprofile.topic_selection.main:app --host 0.0.0.0 --port 8103

对应课题任务书指标 4.2 的"产业科技动态选题"工具，
方案详见 0416-v2.docx 第 X 章"产业科技动态选题"。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from metaprofile.shared.config.settings import settings
from metaprofile.topic_selection.api import routes_feedback, routes_topics

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("topic_selection_starting", env=settings.env)
    yield


app = FastAPI(
    title="产业科技动态选题服务",
    description=(
        "基于多策略融合（热度排序 / 政策关联 / 产业影响力 / 历史去重 / "
        "LLM-RAG 多角度生成）+ LLM 评审员 4 维度打分 + 反馈闭环 的选题生成"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(
    routes_topics.router, prefix=settings.api_prefix, tags=["topics"]
)
app.include_router(
    routes_feedback.router, prefix=settings.api_prefix, tags=["feedback"]
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "topic_selection"}
