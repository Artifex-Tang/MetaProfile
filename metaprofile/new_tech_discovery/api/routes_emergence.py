"""新兴指标 API(Phase B5)。

GET /new-tech/emergence            指标列表(对象×窗口,过滤 object_type/window/quadrant)
POST /new-tech/emergence/compute   触发 Celery 重算
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import (
    TechEmergenceIndicatorORM,
)
from metaprofile.shared.db.session import get_db

router = APIRouter(prefix="/new-tech", tags=["new_tech_discovery"])


class EmergenceItem(BaseModel):
    object_type: str
    object_id: str
    window_month: date
    metrics: dict


class EmergenceList(BaseModel):
    total: int
    items: list[EmergenceItem]


class EmergenceComputeResponse(BaseModel):
    status: str
    detail: str


@router.get("/emergence", response_model=EmergenceList)
async def list_emergence(
    object_type: str | None = Query(default=None, description="ipc_domain|ipc_pair"),
    window: date | None = Query(default=None, description="窗口(年首日)"),
    quadrant: str | None = Query(default=None, description="weak|strong|latent|nswb"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> EmergenceList:
    """查询新兴指标(按窗口降序;quadrant 过滤走 metrics JSONB)。"""
    q = select(TechEmergenceIndicatorORM)
    if object_type:
        q = q.where(TechEmergenceIndicatorORM.object_type == object_type)
    if window:
        q = q.where(TechEmergenceIndicatorORM.window_month == window)
    if quadrant:
        q = q.where(
            TechEmergenceIndicatorORM.metrics["tem_quadrant"].as_string() == quadrant
        )
    rows = (await db.execute(
        q.order_by(TechEmergenceIndicatorORM.window_month.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    total_q = select(TechEmergenceIndicatorORM.id)
    if object_type:
        total_q = total_q.where(TechEmergenceIndicatorORM.object_type == object_type)
    if window:
        total_q = total_q.where(TechEmergenceIndicatorORM.window_month == window)
    if quadrant:
        total_q = total_q.where(
            TechEmergenceIndicatorORM.metrics["tem_quadrant"].as_string() == quadrant
        )
    from sqlalchemy import func
    total = (await db.execute(
        select(func.count()).select_from(total_q.subquery())
    )).scalar() or 0
    return EmergenceList(
        total=int(total),
        items=[
            EmergenceItem(
                object_type=r.object_type, object_id=r.object_id,
                window_month=r.window_month, metrics=r.metrics or {},
            )
            for r in rows
        ],
    )


@router.post("/emergence/compute", response_model=EmergenceComputeResponse)
async def trigger_emergence_compute(
    years_back: int | None = Query(default=None, ge=1, le=30),
    db_connection_id: int | None = Query(default=None),
) -> EmergenceComputeResponse:
    """触发新兴指标重算(Celery 异步;readonly 模式由中间件熔断)。"""
    try:
        from metaprofile.shared.worker.newtech_tasks import compute_emergence

        compute_emergence.delay(years_back=years_back, db_connection_id=db_connection_id)
        return EmergenceComputeResponse(status="queued", detail="compute_emergence 已入队")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"任务入队失败: {exc}") from exc
