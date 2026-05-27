"""技术画像 RAG 补全任务（每周运行）。"""
from __future__ import annotations

import structlog

from metaprofile.profile_tech.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="metaprofile.profile_tech.workers.enrichment_worker.scan_and_enrich"
)
def scan_and_enrich() -> dict:
    """扫描完整度 < 60% 的画像，批量 RAG 补全。

    流程：
    1. SELECT tech_id FROM tech_profile WHERE completeness < 0.60
       ORDER BY <下游近期查询次数 DESC>
    2. 对每个画像调用 foundation.enrichment 模块
       2.1 计算缺失字段
       2.2 RAG 检索（混合 BM25 + Embedding）召回 Top 20 文档
       2.3 LLM Function Calling 抽取缺失字段
       2.4 confidence ≥ 0.8 自动入库
       2.5 0.6 ≤ confidence < 0.8 进入审核队列
       2.6 confidence < 0.6 丢弃
    """
    logger.info("tech_enrichment_started")
    return {"status": "ok", "scanned": 0, "enriched": 0, "queued_for_review": 0}


@celery_app.task(
    name="metaprofile.profile_tech.workers.enrichment_worker.enrich_one"
)
def enrich_one(tech_id: str) -> dict:
    """单个画像的按需补全（被 enrichment API 调用）。"""
    logger.info("tech_single_enrich", tech_id=tech_id)
    return {"status": "ok", "tech_id": tech_id}
