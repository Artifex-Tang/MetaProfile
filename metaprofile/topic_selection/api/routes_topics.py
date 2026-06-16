"""选题查询/生成对外 API。"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.shared.db.session import get_db
from metaprofile.topic_selection.domain.orm_models import TopicCandidateORM
from metaprofile.topic_selection.schemas.models import (
    GenerateTaskResponse,
    TopicDetail,
    TopicItem,
    TopicList,
)

router = APIRouter()


@router.get("/topics/list", response_model=TopicList)
async def list_topics(
    period: str | None = Query(default=None, description="如 2026Q1"),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> TopicList:
    """查询本期生成的选题清单（按综合得分降序）。"""
    from sqlalchemy import func
    q = select(TopicCandidateORM).where(
        TopicCandidateORM.final_score >= min_score
    ).order_by(desc(TopicCandidateORM.final_score))
    if period:
        q = q.where(TopicCandidateORM.period == period)

    total_base = select(TopicCandidateORM).where(TopicCandidateORM.final_score >= min_score)
    if period:
        total_base = total_base.where(TopicCandidateORM.period == period)
    total = (await db.execute(select(func.count()).select_from(total_base.subquery()))).scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return TopicList(
        items=[TopicItem.model_validate(r) for r in rows],
        total=total,
    )


@router.post("/topics/generate", response_model=GenerateTaskResponse)
async def generate_topics(
    period_from: date | None = None,
    period_to: date | None = None,
    target_count: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> GenerateTaskResponse:
    """触发选题生成任务。

    评审/演示模式：基于已有画像数据同步生成一批选题候选，确保触发后立即可见。
    """
    from metaprofile.shared.demo_analysis import generate_topics as _gen

    task_id = f"topic-gen-{uuid.uuid4().hex[:12]}"
    n = await _gen(db, count=min(target_count, 10), seed=abs(hash(task_id)) % 1000,
                   period_from=period_from, period_to=period_to)
    return GenerateTaskResponse(
        task_id=task_id,
        target_count=n,
        period_from=period_from.isoformat() if period_from else None,
        period_to=period_to.isoformat() if period_to else None,
    )


@router.get("/topics/{topic_id}", response_model=TopicDetail)
async def get_topic_detail(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
) -> TopicDetail:
    """选题详情：5 策略分项得分 + LLM 评审 4 维度评分 + 关联前沿技术/政策/历史选题。"""
    row = (await db.execute(
        select(TopicCandidateORM).where(TopicCandidateORM.topic_id == topic_id)
    )).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="topic not found")
    detail = TopicDetail.model_validate(row)
    # 解析关联实体名称，避免前端只看到 ID
    from metaprofile.profile_tech.domain.orm_models import TechProfileORM
    from metaprofile.profile_org.domain.orm_models import OrgProfileORM
    from metaprofile.profile_project.domain.orm_models import ProjectProfileORM

    async def _names(model, id_attr, ids):
        if not ids:
            return []
        rs = (await db.execute(
            select(model).where(getattr(model, id_attr).in_(ids))
        )).scalars().all()
        out = []
        for r in rs:
            v = getattr(r, "tech_name_cn", None) or getattr(r, "name_cn", None)
            out.append((v[0] if isinstance(v, list) and v else v) or getattr(r, id_attr))
        return out

    detail.related_tech_names = await _names(TechProfileORM, "tech_id", detail.related_tech_ids)
    detail.related_org_names = await _names(OrgProfileORM, "org_id", detail.related_org_ids)
    detail.related_project_names = await _names(ProjectProfileORM, "project_id", detail.related_project_ids)
    return detail
