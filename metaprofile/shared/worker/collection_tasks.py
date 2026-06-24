"""collection celery 任务：scheduled_task task_type=collection → 跑 run_sql_warehouse_collection。

run_async 复用 worker 持久 loop（非 asyncio.run，避免 asyncpg 跨任务 loop bug）。
镜像 translate_tasks：_async_X(...)(开 get_session,干活) + @celery_app.task(bind=True) X → run_async。
"""
from __future__ import annotations

import structlog
from typing import Any

from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.worker.async_runner import run_async
from metaprofile.shared.worker.celery_app import celery_app
from metaprofile.settings_api.domain.orm_models import (
    CollectionTaskORM,
    DataSourceConfigORM,
)
from metaprofile.ingest_ods.collectors.sql_warehouse import run_sql_warehouse_collection

logger = structlog.get_logger(__name__)


async def _async_run_collection(source_id: int) -> dict[str, Any]:
    """加载 DataSourceConfigORM → 建 CollectionTaskORM 行 → 跑采集 → 终态落库。

    source_id 不存在 → 返回 error dict（不抛,不建 task 行）。
    采集异常 → task.status=failed + error_msg + commit, 返回 failed dict（不向上抛,
    避免 celery worker 把异常重试成风暴）。
    """
    try:
        async with get_session() as session:
            source = await session.get(DataSourceConfigORM, source_id)
            if source is None:
                logger.warning("collection_source_not_found", source_id=source_id)
                return {
                    "status": "error",
                    "error": f"DataSourceConfig {source_id} not found",
                }

            task = CollectionTaskORM(
                source_id=source.id,
                source_name=source.name,
                profile_type=source.profile_type,
                status="running",
            )
            session.add(task)
            await session.flush()  # 拿 task.id

            try:
                imported = await run_sql_warehouse_collection(
                    task=task, source=source, session=session
                )
                task.status = "completed"
                task.records_imported = imported
                result = {
                    "status": "completed",
                    "imported": imported,
                    "task_id": task.id,
                }
            except Exception as exc:  # noqa: BLE001  采集失败不杀 worker
                logger.exception("collection_failed", source_id=source_id, error=str(exc))
                task.status = "failed"
                task.error_msg = str(exc)
                result = {
                    "status": "failed",
                    "error": str(exc),
                    "task_id": task.id,
                }
            await session.commit()
            return result
    except Exception as exc:  # noqa: BLE001  session/flush 层故障兜底
        logger.exception("collection_session_failed", source_id=source_id, error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.collection.run", bind=True)
def run_collection(self, source_id: int) -> dict[str, Any]:
    return run_async(_async_run_collection(source_id))
