"""扫描监测告警 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.scan_monitor.domain.orm_models import ScanAlertORM
from metaprofile.scan_monitor.schemas.models import AlertItem, AlertList
from metaprofile.shared.db.session import get_db

router = APIRouter()


@router.get("/frontier-tech/alerts", response_model=AlertList)
async def list_alerts(
    severity: str | None = Query(default=None, description="info / warn / critical"),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
) -> AlertList:
    """查询前沿技术告警列表（信号突变、TRL 升级、关键机构布局变更等）。"""
    from sqlalchemy import func
    q = select(ScanAlertORM).order_by(desc(ScanAlertORM.fired_at))
    if severity:
        q = q.where(ScanAlertORM.severity == severity)
    total_q = select(ScanAlertORM)
    if severity:
        total_q = total_q.where(ScanAlertORM.severity == severity)
    total_row = await db.execute(select(func.count()).select_from(total_q.subquery()))
    total = total_row.scalar_one()
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return AlertList(
        items=[AlertItem.model_validate(r) for r in rows],
        total=total,
    )
