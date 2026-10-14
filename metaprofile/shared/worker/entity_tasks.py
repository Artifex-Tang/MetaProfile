"""实体挖掘 celery 任务(Phase D):机构归一 / 作者消歧 / 项目分类。"""
from __future__ import annotations

from typing import Any

import structlog

from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.worker.async_runner import run_async
from metaprofile.shared.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _run_org_normalize(db_connection_id: int | None, use_ror: bool) -> dict[str, Any]:
    from metaprofile.entity_mining.services.org_normalizer import OrgNormalizerService

    try:
        async with get_session() as session:
            res = await OrgNormalizerService(db_connection_id).suggest(
                session, use_ror=use_ror,
            )
            await session.commit()
            return res
    except Exception as exc:  # noqa: BLE001
        logger.warning("org_normalize_task_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.entity.org_normalize")
def org_normalize(
    db_connection_id: int | None = None, use_ror: bool = True,
) -> dict[str, Any]:
    """D1:机构 ROR 归一建议。"""
    return run_async(_run_org_normalize(db_connection_id, use_ror))


async def _run_author_dedup(db_connection_id: int | None) -> dict[str, Any]:
    from metaprofile.entity_mining.services.author_dedup import suggest_author_merges

    try:
        async with get_session() as session:
            res = await suggest_author_merges(session, db_connection_id=db_connection_id)
            await session.commit()
            return res
    except Exception as exc:  # noqa: BLE001
        logger.warning("author_dedup_task_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.entity.author_dedup")
def author_dedup(db_connection_id: int | None = None) -> dict[str, Any]:
    """D2:作者消歧合并建议(规则版)。"""
    return run_async(_run_author_dedup(db_connection_id))


async def _run_project_classify(max_projects: int) -> dict[str, Any]:
    from metaprofile.entity_mining.services.project_classify import classify_projects

    try:
        async with get_session() as session:
            res = await classify_projects(session, max_projects=max_projects)
            await session.commit()
            return res
    except Exception as exc:  # noqa: BLE001
        logger.warning("project_classify_task_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.entity.project_classify")
def project_classify(max_projects: int = 50) -> dict[str, Any]:
    """D3:项目 LLM 分类 → IPC 域。"""
    return run_async(_run_project_classify(max_projects))
