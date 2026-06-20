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
