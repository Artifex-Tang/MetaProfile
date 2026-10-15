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


async def _async_emergence(years_back: int | None,
                           db_connection_id: int | None) -> dict[str, Any]:
    from metaprofile.new_tech_discovery.services.emergence_service import (
        EmergenceService,
    )

    try:
        svc = EmergenceService(db_connection_id=db_connection_id)
        return await svc.compute(years_back=years_back)
    except Exception as exc:  # noqa: BLE001
        logger.warning("emergence_task_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.newtech.compute_emergence")
def compute_emergence(
    years_back: int | None = None,
    db_connection_id: int | None = None,
) -> dict[str, Any]:
    """新兴指标计算(Phase B):Doris 专利 → Porter/TLC/TEM/Salton → 指标表。"""
    return run_async(_async_emergence(years_back, db_connection_id))


async def _async_disruption(years_back: int | None, db_connection_id: int | None,
                            llm: bool | None) -> dict[str, Any]:
    from metaprofile.new_tech_discovery.services.disruption_service import (
        DisruptionService,
    )

    try:
        svc = DisruptionService(db_connection_id=db_connection_id)
        return await svc.compute(years_back=years_back, llm=llm)
    except Exception as exc:  # noqa: BLE001
        logger.warning("disruption_task_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.newtech.compute_disruption")
def compute_disruption(
    years_back: int | None = None,
    db_connection_id: int | None = None,
    llm: bool | None = None,
) -> dict[str, Any]:
    """颠覆性评估(Phase C):组件 z 合分 + 漏斗 LLM Rotolo rubric。"""
    return run_async(_async_disruption(years_back, db_connection_id, llm))


async def _async_tech_graph() -> dict[str, Any]:
    from metaprofile.new_tech_discovery.services.tech_graph_service import (
        build_cooccurrence_edges,
        build_temporal_evolve_edges,
    )

    try:
        async with get_session() as session:
            co = await build_cooccurrence_edges(session)
            ev = await build_temporal_evolve_edges(session)
            await session.commit()
            return {"status": "done", "cooccurrence": co, "evolve": ev}
    except Exception as exc:  # noqa: BLE001
        logger.warning("tech_graph_task_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.newtech.build_tech_graph")
def build_tech_graph() -> dict[str, Any]:
    """tech-tech 真挖掘(Phase E4/E5):共现网 + 时序演进链 → Neo4j。"""
    return run_async(_async_tech_graph())


async def _async_evolve_llm(top_n: int) -> dict[str, Any]:
    from metaprofile.new_tech_discovery.services.evolve_llm import (
        build_llm_evolve_edges,
    )

    try:
        async with get_session() as session:
            res = await build_llm_evolve_edges(session, top_n=top_n)
            await session.commit()
            return res
    except Exception as exc:  # noqa: BLE001
        logger.warning("evolve_llm_task_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.newtech.build_evolve_llm")
def build_evolve_llm(top_n: int = 200) -> dict[str, Any]:
    """E5 LLM 演进链:共现概念对 → LLM 判向 → TECH_EVOLVE(conf 0.7·c)。"""
    return run_async(_async_evolve_llm(top_n))
