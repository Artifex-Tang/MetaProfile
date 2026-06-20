"""scheduled_task CRUD + 立即执行。

注：collection cron 同步(DataSourceConfig.schedule_cron → scheduled_task) +
collection 触发 dispatch 留 follow-up（trigger_collection 走 asyncio.create_task，
celery worker wiring 复杂）；当前 scheduler 仅 translate_batch 端到端可用。
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.settings_api.domain.orm_models import ScheduledTaskORM
from metaprofile.shared.scheduler.poller import dispatch

logger = structlog.get_logger(__name__)


async def list_tasks(session: AsyncSession) -> list[ScheduledTaskORM]:
    return (await session.execute(
        select(ScheduledTaskORM).order_by(ScheduledTaskORM.id)
    )).scalars().all()


async def get_task(session: AsyncSession, task_id: int) -> ScheduledTaskORM | None:
    return await session.get(ScheduledTaskORM, task_id)


async def create_task(session: AsyncSession, **fields) -> ScheduledTaskORM:
    task = ScheduledTaskORM(**fields)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(session: AsyncSession, task_id: int, **fields) -> ScheduledTaskORM | None:
    task = await session.get(ScheduledTaskORM, task_id)
    if task is None:
        return None
    for k, v in fields.items():
        if v is not None and hasattr(task, k):
            setattr(task, k, v)
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task_id: int) -> bool:
    task = await session.get(ScheduledTaskORM, task_id)
    if task is None:
        return False
    await session.delete(task)
    await session.commit()
    return True


async def run_now(session: AsyncSession, task_id: int) -> str:
    """立即执行：直接 dispatch（绕 poller），更新 last_run_at。返 celery task id。"""
    task = await session.get(ScheduledTaskORM, task_id)
    if task is None:
        raise ValueError("scheduled task not found")
    celery_id = await dispatch(task_type=task.task_type, params=task.params or {})
    task.last_run_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    task.last_status = "ok" if celery_id else "failed"
    await session.commit()
    return celery_id
