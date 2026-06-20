"""new_tech_discovery celery 任务：弱信号提取（ingest hook / UI 按钮均 .delay() 入队）。

跑 WeakSignalExtractor.extract → 落 weak_signal → 对每条信号建关联网络边
（NetworkCorrelator）。重任务（jieba 分词 + 多源 Doris 读 + metric），故异步。

复用 worker 持久 loop（见 async_runner）避免 asyncpg 跨任务 'Event loop is closed'。
"""
from __future__ import annotations

from datetime import date
from typing import Any

import structlog
from sqlalchemy import select

from metaprofile.new_tech_discovery.domain.orm_models import WeakSignalORM
from metaprofile.new_tech_discovery.services.network_correlator import NetworkCorrelator
from metaprofile.new_tech_discovery.services.weak_signal_extractor import WeakSignalExtractor
from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.worker.async_runner import run_async
from metaprofile.shared.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _async_extract(
    period_from: date,
    period_to: date,
    domain: str | None,
    db_connection_id: int | None,
    task_id: str,
) -> dict[str, Any]:
    try:
        async with get_session() as session:
            ext = WeakSignalExtractor(db_connection_id=db_connection_id)
            signals = await ext.extract(
                db=session, domain=domain,
                period_from=period_from, period_to=period_to,
            )
            # 对刚落的每条信号建关联网络边
            rows = (
                await session.execute(
                    select(WeakSignalORM).where(
                        WeakSignalORM.period_from == period_from,
                        WeakSignalORM.period_to == period_to,
                    )
                )
            ).scalars().all()
            correlator = NetworkCorrelator(session)
            edge_count = 0
            for row in rows:
                edges = await correlator.build_network(
                    signal=row, period_from=period_from, period_to=period_to,
                )
                edge_count += len(edges)
            await session.commit()
            logger.info(
                "weak_signal_task_done",
                task_id=task_id, signals=len(signals), edges=edge_count,
            )
            return {"status": "done", "signals": len(signals), "edges": edge_count}
    except Exception as exc:  # noqa: BLE001
        logger.warning("weak_signal_task_failed", task_id=task_id, error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.newtech.extract_weak_signals", bind=True)
def extract_weak_signals(
    self,
    period_from: str,
    period_to: str,
    domain: str | None = None,
    db_connection_id: int | None = None,
) -> dict[str, Any]:
    """同步 celery 任务入口：解析日期 → 在 worker 持久 loop 上跑 _async_extract。"""
    pf = date.fromisoformat(period_from)
    pt = date.fromisoformat(period_to)
    return run_async(_async_extract(pf, pt, domain, db_connection_id, self.request.id))
