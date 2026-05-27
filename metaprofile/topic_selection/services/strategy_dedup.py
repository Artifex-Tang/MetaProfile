"""策略 D：历史选题去重。

基于 Jaccard 相似度比较候选标题与历史选题库，得分越高表示越独特。
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.topic_selection.domain.orm_models import TopicCandidateORM

logger = structlog.get_logger(__name__)


def _jaccard(a: str, b: str) -> float:
    """字符级 Jaccard 相似度（中文友好）。"""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union > 0 else 0.0


class DedupStrategyScorer:
    """历史去重策略评分器。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def score(self, title: str, max_history: int = 200) -> float:
        """返回 [0, 1] 独特性分：1 - 与历史最相似选题的 Jaccard 相似度。"""
        history_titles = await self._fetch_history_titles(max_history)
        if not history_titles:
            return 1.0
        max_sim = max(_jaccard(title, h) for h in history_titles)
        return 1.0 - max_sim

    async def _fetch_history_titles(self, limit: int) -> list[str]:
        try:
            rows = await self._db.execute(
                select(TopicCandidateORM.title)
                .where(TopicCandidateORM.status.in_(["accepted", "rejected"]))
                .order_by(TopicCandidateORM.id.desc())
                .limit(limit)
            )
            return [row[0] for row in rows.all()]
        except Exception as exc:
            logger.warning("dedup_history_fetch_failed", error=str(exc))
            return []
