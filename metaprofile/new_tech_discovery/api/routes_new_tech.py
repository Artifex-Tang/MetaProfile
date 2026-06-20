"""新技术发现对外 API。"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import WeakSignalORM
from metaprofile.new_tech_discovery.schemas.models import (
    ScanTaskResponse,
    WeakSignalItem,
    WeakSignalList,
)
from metaprofile.shared.db.session import get_db
from metaprofile.shared.worker.newtech_tasks import extract_weak_signals

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
async def trigger_scan(
    domain: str | None = None,
    db_connection_id: int | None = Query(default=None),
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
) -> ScanTaskResponse:
    """手动触发新技术扫描（弱信号提取）—— 异步 Celery 任务。

    db_connection_id 缺省 → 用 settings.weak_signal.corpus_db_connection_id；
    若仍无（开发环境无 Doris）→ 降级 demo_analysis.generate_signals 保证 UI 可见。
    """
    from datetime import timedelta

    from metaprofile.shared.config.settings import settings
    from metaprofile.shared.demo_analysis import generate_signals

    task_id = f"ntd-scan-{uuid.uuid4().hex[:12]}"
    today = date.today()
    period_from = today - timedelta(days=days)

    conn_id = db_connection_id or settings.weak_signal.corpus_db_connection_id
    if conn_id is None:
        # 无 Doris 配置 → demo 兜底（同步生成，UI 立即可见）
        await generate_signals(db, period_from=period_from, period_to=today,
                               count=8, seed=abs(hash(task_id)) % 1000)
        return ScanTaskResponse(task_id=task_id, domain=domain, status="demo")

    result = extract_weak_signals.delay(
        period_from.isoformat(), today.isoformat(), domain, conn_id,
    )
    return ScanTaskResponse(task_id=result.id or task_id, domain=domain, status="queued")
