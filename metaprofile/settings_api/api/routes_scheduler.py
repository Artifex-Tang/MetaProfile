"""定时任务(scheduled_task)管理 + 批量翻译 API。

scheduled_task CRUD + 立即执行 + cron 校验；批量翻译触发。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from croniter import croniter

from metaprofile.settings_api.services.scheduler_service import (
    create_task, delete_task, get_task, list_tasks, run_now, update_task,
)
from metaprofile.shared.db.session import get_db
from metaprofile.shared.worker.translate_tasks import batch_translate_names

router = APIRouter(prefix="/api/v1/settings", tags=["scheduled-tasks"])

_ALLOWED_TASK_TYPES = {"translate_batch", "collection"}


@router.get("/scheduled-tasks")
async def get_scheduled_tasks(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = await list_tasks(db)
    return [_to_dict(r) for r in rows]


@router.post("/scheduled-tasks")
async def post_scheduled_task(payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    cron = payload.get("cron", "")
    if not croniter.is_valid(cron):
        raise HTTPException(422, "非法 cron 表达式")
    if payload.get("task_type") not in _ALLOWED_TASK_TYPES:
        raise HTTPException(422, f"task_type 必须为 {_ALLOWED_TASK_TYPES}")
    task = await create_task(
        db,
        name=payload["name"],
        task_type=payload["task_type"],
        cron=cron,
        params=payload.get("params", {}),
        enabled=payload.get("enabled", True),
    )
    return _to_dict(task)


@router.patch("/scheduled-tasks/{task_id}")
async def patch_scheduled_task(task_id: int, payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    if "cron" in payload and not croniter.is_valid(payload["cron"]):
        raise HTTPException(422, "非法 cron 表达式")
    task = await update_task(db, task_id, **payload)
    if task is None:
        raise HTTPException(404, "scheduled task not found")
    return _to_dict(task)


@router.delete("/scheduled-tasks/{task_id}")
async def delete_scheduled_task(task_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    ok = await delete_task(db, task_id)
    if not ok:
        raise HTTPException(404, "scheduled task not found")
    return {"deleted": True}


@router.post("/scheduled-tasks/{task_id}/run")
async def run_scheduled_task(task_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        celery_id = await run_now(db, task_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"task_id": celery_id, "queued": bool(celery_id)}


@router.post("/translate/batch")
async def batch_translate(
    entity_type: str | None = Query(default=None), db: AsyncSession = Depends(get_db),
) -> dict:
    """批量翻译 name_cn 空的实体。entity_type 缺省=全部 4 类。"""
    res = batch_translate_names.delay(entity_type)
    return {"task_id": res.id}


def _to_dict(r) -> dict:
    return {
        "id": r.id, "name": r.name, "task_type": r.task_type, "cron": r.cron,
        "params": r.params, "enabled": r.enabled,
        "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
        "last_status": r.last_status,
    }
