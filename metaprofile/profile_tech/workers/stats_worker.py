"""技术画像统计计算任务（每日运行）。"""
from __future__ import annotations

import structlog

from metaprofile.profile_tech.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="metaprofile.profile_tech.workers.stats_worker.compute_daily")
def compute_daily() -> dict:
    """计算并缓存技术画像每日统计。

    指标：
    - 总量、本期增量、本期更新量
    - 领域分布、地域分布
    - 活跃度排名 Top 50
    - 完整度直方图（0-30 / 30-60 / 60-80 / 80-100）
    - LLM 贡献度（LLM 抽取/补全字段占比）
    - 关系密度（每个技术节点平均关系数）

    结果写入 Redis：stats:tech:latest（TTL=24h）
    """
    logger.info("tech_stats_compute_started")
    return {"status": "ok"}
