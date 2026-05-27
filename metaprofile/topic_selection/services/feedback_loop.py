"""反馈闭环：录入审核意见，统计策略权重偏差，供未来权重自适应调整。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.topic_selection.domain.orm_models import TopicCandidateORM, TopicFeedbackORM

logger = structlog.get_logger(__name__)


class FeedbackLoopService:
    """选题反馈处理服务。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(
        self,
        *,
        topic_id: str,
        rating: Literal["accept", "reject", "revise"],
        score: int,
        comments: str | None,
        operator: str,
    ) -> TopicFeedbackORM:
        feedback = TopicFeedbackORM(
            topic_id=topic_id,
            rating=rating,
            score=score,
            comments=comments,
            operator=operator,
        )
        self._db.add(feedback)

        # 更新 TopicCandidateORM.status 冗余字段
        row = (await self._db.execute(
            select(TopicCandidateORM).where(TopicCandidateORM.topic_id == topic_id)
        )).scalars().first()
        if row is not None:
            row.status = {"accept": "accepted", "reject": "rejected", "revise": "revised"}[rating]

        await self._db.flush()
        return feedback

    async def compute_acceptance_rate(self) -> float:
        """返回历史选题通过率（accept / total）。"""
        try:
            total_row = await self._db.execute(
                select(func.count(TopicFeedbackORM.id))
            )
            total = total_row.scalar_one()
            if total == 0:
                return 0.0
            accept_row = await self._db.execute(
                select(func.count(TopicFeedbackORM.id)).where(
                    TopicFeedbackORM.rating == "accept"
                )
            )
            accepted = accept_row.scalar_one()
            return accepted / total
        except Exception as exc:
            logger.warning("feedback_acceptance_rate_failed", error=str(exc))
            return 0.0
