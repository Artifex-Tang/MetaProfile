"""enrich 任务记录持久化：trigger 写 queued 行，worker 写终态。

celery AsyncResult 过期即丢，前端轮询外无法回看历史；故落 enrichment_tasks 表，
让 Settings 任务列表能展示 LLM 补全任务（与采集任务同列）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.settings_api.domain.orm_models import EnrichmentTaskORM

TERMINAL = {"done", "skipped", "no_fill", "failed", "error"}


async def create_task(
    session: AsyncSession,
    *,
    profile_type: str,
    entity_id: str,
    task_id: str,
    entity_name: str | None = None,
) -> None:
    """trigger 派发 celery 任务后调用：写一条 queued 记录。"""
    session.add(
        EnrichmentTaskORM(
            profile_type=profile_type,
            entity_id=entity_id,
            task_id=task_id,
            entity_name=entity_name,
            status="queued",
        )
    )
    await session.flush()


async def finish_task(
    session: AsyncSession,
    *,
    task_id: str,
    status: str,
    filled_fields: list[str] | None = None,
    error_msg: str | None = None,
) -> None:
    """worker 完成后调用：更新终态 + completed_at。行不存在则静默（兼容未落库的旧任务）。"""
    values: dict[str, Any] = {
        "status": status,
        "completed_at": datetime.now(timezone.utc),
    }
    if status == "running" and "started_at" not in values:
        values["started_at"] = datetime.now(timezone.utc)
    if filled_fields is not None:
        values["filled_fields"] = filled_fields
    if error_msg:
        values["error_msg"] = error_msg[:500]
    await session.execute(
        update(EnrichmentTaskORM)
        .where(EnrichmentTaskORM.task_id == task_id)
        .values(**values)
    )
