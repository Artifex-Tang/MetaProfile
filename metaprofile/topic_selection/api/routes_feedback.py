"""选题反馈闭环 API。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.shared.db.session import get_db
from metaprofile.topic_selection.schemas.models import FeedbackResponse
from metaprofile.topic_selection.services.feedback_loop import FeedbackLoopService

router = APIRouter()


class TopicFeedback(BaseModel):
    rating: Literal["accept", "reject", "revise"]
    score: int = Field(..., ge=1, le=5)
    comments: str | None = None
    operator: str


@router.post("/topics/{topic_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    topic_id: str,
    payload: TopicFeedback,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """选题反馈：录入审核意见，反馈数据用于策略权重在线学习。"""
    svc = FeedbackLoopService(db)
    await svc.record(
        topic_id=topic_id,
        rating=payload.rating,
        score=payload.score,
        comments=payload.comments,
        operator=payload.operator,
    )
    await db.commit()
    return FeedbackResponse(topic_id=topic_id)
