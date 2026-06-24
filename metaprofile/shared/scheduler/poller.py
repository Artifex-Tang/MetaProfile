"""通用 cron 调度 poller：scheduler_tick(60s beat) 读 scheduled_task，到期 dispatch。

到期判定 is_due：croniter 算 last_run_at（无则 epoch）之后的下一次触发时间，<=now 即到期。
task_type→celery 任务 由 TASK_DISPATCH 注册表懒构造（import 时 celery app 可能未就绪）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from croniter import croniter

_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


def is_due(cron: str, last_run_at: datetime | None, now: datetime) -> bool:
    """cron 自 last_run_at（None→epoch）后下一次触发时间 <= now → 到期。

    非法 cron 抛 ValueError（供端点 422 校验）。
    """
    if not croniter.is_valid(cron):
        raise ValueError(f"非法 cron 表达式: {cron}")
    base = last_run_at or _EPOCH
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    next_fire = croniter(cron, base).get_next(datetime)
    return next_fire <= now


import structlog  # noqa: E402
from sqlalchemy import select  # noqa: E402

from metaprofile.settings_api.domain.orm_models import ScheduledTaskORM  # noqa: E402

logger = structlog.get_logger(__name__)

# task_type → 同步调用（返 celery AsyncResult）；懒构造防 import 循环
TASK_DISPATCH: dict[str, object] = {}


def _build_registry() -> dict[str, object]:
    from metaprofile.shared.worker.translate_tasks import batch_translate_names
    from metaprofile.shared.worker.collection_tasks import run_collection
    return {
        "translate_batch": lambda **p: batch_translate_names.delay(p.get("entity_type")),
        # task_type=collection → celery worker 跑 run_sql_warehouse_collection（5 阶段灌库）
        "collection": lambda **p: run_collection.delay(p.get("source_id")),
    }


def _ensure_registry() -> dict[str, object]:
    global TASK_DISPATCH
    if not TASK_DISPATCH:
        TASK_DISPATCH = _build_registry()
    return TASK_DISPATCH


async def dispatch(*, task_type: str, params: dict) -> str:
    """按 task_type dispatch 对应 celery 任务，返 task id（未知类型返 ''）。"""
    registry = _ensure_registry()
    fn = registry.get(task_type)
    if fn is None:
        logger.warning("scheduler_unknown_task_type", task_type=task_type)
        return ""
    result = fn(**(params or {}))
    return getattr(result, "id", "") or ""


async def tick(session, *, now: datetime | None = None) -> dict:
    """扫 enabled scheduled_task，到期即 dispatch + 更新 last_run_at/last_status。"""
    now = now or datetime.now(timezone.utc)
    rows = (await session.execute(
        select(ScheduledTaskORM).where(ScheduledTaskORM.enabled.is_(True))
    )).scalars().all()
    dispatched = 0
    for t in rows:
        try:
            if not is_due(t.cron, t.last_run_at, now):
                continue
            t.last_status = "running"
            await session.flush()
            await dispatch(task_type=t.task_type, params=t.params or {})
            t.last_run_at = now
            t.last_status = "ok"
            dispatched += 1
        except Exception as exc:  # noqa: BLE001  单任务失败不杀整轮
            t.last_status = "failed"
            logger.warning("scheduler_dispatch_failed", task=t.name, error=str(exc))
    await session.commit()
    return {"dispatched": dispatched, "total": len(rows)}


# celery beat 每 60s 触发 scheduler_tick（在 celery_app.beat_schedule 注册）
def _register_celery_task() -> None:
    from metaprofile.shared.db.postgres import get_session
    from metaprofile.shared.worker.async_runner import run_async
    from metaprofile.shared.worker.celery_app import celery_app

    @celery_app.task(name="metaprofile.scheduler.tick")
    def scheduler_tick():  # type: ignore[no-redef]
        async def _run():
            async with get_session() as session:
                return await tick(session)
        return run_async(_run())


_register_celery_task()
