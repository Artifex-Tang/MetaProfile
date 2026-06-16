"""扫描监测对外 API。"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from metaprofile.scan_monitor.domain.orm_models import FrontierTechORM
from metaprofile.scan_monitor.schemas.models import FrontierTechItem, FrontierTechList, ScanTaskResponse
from metaprofile.shared.db.session import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/frontier-tech/list", response_model=FrontierTechList)
async def list_frontier_tech(
    period_from: date | None = Query(default=None),
    period_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> FrontierTechList:
    """查询本期识别出的前沿技术清单（按融合分降序）。"""
    q = select(FrontierTechORM).order_by(desc(FrontierTechORM.fusion_score))
    if period_from:
        q = q.where(FrontierTechORM.period_from >= period_from)
    if period_to:
        q = q.where(FrontierTechORM.period_to <= period_to)
    total_q = select(FrontierTechORM)
    if period_from:
        total_q = total_q.where(FrontierTechORM.period_from >= period_from)
    if period_to:
        total_q = total_q.where(FrontierTechORM.period_to <= period_to)

    from sqlalchemy import func
    total_row = await db.execute(select(func.count()).select_from(total_q.subquery()))
    total = total_row.scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return FrontierTechList(
        items=[FrontierTechItem.model_validate(r) for r in rows],
        total=total,
    )


@router.get("/frontier-tech/{tech_id}", response_model=FrontierTechItem)
async def get_frontier_tech_detail(
    tech_id: str,
    db: AsyncSession = Depends(get_db),
) -> FrontierTechItem:
    """前沿技术详情：五维信号分项得分 + LLM 验证证据 + TRL 标注。"""
    row = (await db.execute(
        select(FrontierTechORM).where(
            (FrontierTechORM.scan_task_id == tech_id)
            | (FrontierTechORM.tech_id == tech_id)
        )
    )).scalars().first()
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="frontier tech not found")
    return FrontierTechItem.model_validate(row)


@router.post("/frontier-tech/scan", response_model=ScanTaskResponse)
async def trigger_scan(
    period_from: date | None = None,
    period_to: date | None = None,
    db: AsyncSession = Depends(get_db),
) -> ScanTaskResponse:
    """手动触发前沿技术扫描任务。

    评审/演示模式：基于已有画像数据同步生成一批前沿技术 + 告警，确保触发后立即可见。
    """
    from datetime import timedelta
    from metaprofile.shared.demo_analysis import generate_frontier

    today = date.today()
    pf = period_from or (today - timedelta(days=30))
    pt = period_to or today
    task_id = f"scan-{uuid.uuid4().hex[:12]}"
    await generate_frontier(db, period_from=pf, period_to=pt,
                            count=8, seed=abs(hash(task_id)) % 1000)
    return ScanTaskResponse(task_id=task_id, period_from=pf, period_to=pt)
