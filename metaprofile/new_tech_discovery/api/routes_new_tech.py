"""新技术发现对外 API。"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import WeakSignalORM
from metaprofile.new_tech_discovery.schemas.models import ScanTaskResponse, WeakSignalItem, WeakSignalList
from metaprofile.shared.db.session import get_db

router = APIRouter()


@router.get("/new-tech/list", response_model=WeakSignalList)
async def list_new_tech(
    domain: str | None = Query(default=None),
    period: str | None = Query(default=None, description="如 2026Q1"),
    min_strength: float = Query(default=0.0, ge=0.0, le=1.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> WeakSignalList:
    """查询本期发现的新技术清单（按弱信号强度降序）。"""
    from sqlalchemy import func
    q = select(WeakSignalORM).where(
        WeakSignalORM.strength >= min_strength
    ).order_by(desc(WeakSignalORM.strength))
    if domain:
        q = q.where(WeakSignalORM.domain == domain)

    total_q = select(WeakSignalORM).where(WeakSignalORM.strength >= min_strength)
    if domain:
        total_q = total_q.where(WeakSignalORM.domain == domain)
    total_row = await db.execute(select(func.count()).select_from(total_q.subquery()))
    total = total_row.scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return WeakSignalList(
        items=[WeakSignalItem.model_validate(r) for r in rows],
        total=total,
    )


@router.post("/new-tech/scan", response_model=ScanTaskResponse)
async def trigger_scan(domain: str | None = None) -> ScanTaskResponse:
    """手动触发新技术扫描任务（异步）。"""
    task_id = f"ntd-scan-{uuid.uuid4().hex[:12]}"
    return ScanTaskResponse(task_id=task_id, domain=domain)
