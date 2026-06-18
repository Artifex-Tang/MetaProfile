from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.shared.db.session import get_db
from metaprofile.settings_api.domain.orm_models import CollectionTaskORM, DataSourceConfigORM
from metaprofile.settings_api.schemas.models import CollectionTaskOut, CollectionTaskStats, TriggerCollectionResponse
from metaprofile.settings_api.services.collector_service import get_task_stats, trigger_collection

router = APIRouter(prefix="/api/v1/settings/collection", tags=["采集任务"])


@router.post("/trigger/{ds_id}", response_model=TriggerCollectionResponse, status_code=202)
async def trigger(ds_id: int, db: AsyncSession = Depends(get_db)):
    ds = await db.get(DataSourceConfigORM, ds_id)
    if not ds:
        raise HTTPException(404, "数据源不存在")
    if not ds.is_enabled:
        raise HTTPException(400, "数据源已禁用，请先启用")

    task = await trigger_collection(ds, db)
    return TriggerCollectionResponse(
        task_id=task.id,
        source_id=ds.id,
        source_name=ds.name,
        status="pending",
        message="采集任务已提交，后台执行中",
    )


@router.get("/tasks", response_model=list[CollectionTaskOut])
async def list_tasks(
    source_id: int | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(CollectionTaskORM).order_by(desc(CollectionTaskORM.id)).limit(limit)
    if source_id is not None:
        q = q.where(CollectionTaskORM.source_id == source_id)
    rows = (await db.execute(q)).scalars().all()
    return rows


@router.get("/tasks/{task_id}", response_model=CollectionTaskOut)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(CollectionTaskORM, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/tasks/{task_id}/stats", response_model=CollectionTaskStats)
async def get_task_statistics(task_id: int, db: AsyncSession = Depends(get_db)):
    """采集任务运行统计（ingest_raw / ingest_errors 聚合）。"""
    task = await db.get(CollectionTaskORM, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return await get_task_stats(db, task_id)
