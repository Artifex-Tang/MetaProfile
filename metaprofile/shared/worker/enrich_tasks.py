"""enrich celery 任务：4 画像共享，包裹 shared/enrich/orm_enricher 核心。

任务（同步 celery 任务体内用 asyncio.run 跑异步补全核心）：
- enrich_tech(tech_id) / enrich_project(project_id) / enrich_org(org_id) / enrich_person(person_id)

每个任务：开 session → 调 orm_enricher.enrich_one（直写 typed ORM）→ 返回结果 dict。
"""
from __future__ import annotations

import asyncio
import structlog
from typing import Any

from metaprofile.foundation.enrichment.llm_filler import LLMFieldFiller
from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_person.domain.orm_models import PersonProfileORM
from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.enrich.orm_enricher import EnrichOutcome, enrich_one
from metaprofile.shared.enrich.task_log import finish_task
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _shape(outcome: EnrichOutcome, entity_id: str) -> dict[str, Any]:
    if outcome.error:
        status = "error"
    elif outcome.skipped:
        status = "skipped"
    else:
        status = "done" if outcome.filled_fields else "no_fill"
    return {
        "status": status,
        "entity_id": entity_id,
        "completeness_before": outcome.completeness_before,
        "completeness_after": outcome.completeness_after,
        "filled_fields": outcome.filled_fields,
        "error": outcome.error,
    }


def _outcome_status(outcome: EnrichOutcome) -> str:
    if outcome.error:
        return "error"
    if outcome.skipped:
        return "skipped"
    return "done" if outcome.filled_fields else "no_fill"


async def _async_run(
    entity_type: EntityType,
    orm_cls: type,
    change_log_entity_type: str,
    entity_id: str,
    task_id: str,
) -> EnrichOutcome:
    """跑补全 + 回写 EnrichmentTaskORM 终态（供任务列表查看历史）。

    异常时标 failed 再 raise，避免行永远卡 queued。
    """
    try:
        async with get_session() as session:
            outcome = await enrich_one(
                session=session,
                entity_type=entity_type,
                orm_cls=orm_cls,
                entity_id=entity_id,
                filler=LLMFieldFiller(LLMGateway()),
                change_log_entity_type=change_log_entity_type,
            )
            await finish_task(
                session, task_id=task_id, status=_outcome_status(outcome),
                filled_fields=outcome.filled_fields, error_msg=outcome.error,
            )
            return outcome
    except Exception as exc:
        try:
            async with get_session() as session:
                await finish_task(
                    session, task_id=task_id, status="failed", error_msg=str(exc),
                )
        except Exception:  # noqa: BLE001 — 日志写失败不应掩盖原始补全异常
            logger.warning("enrich_task_log_failed", task_id=task_id, error=str(exc))
        raise


def _run(
    entity_type: EntityType,
    orm_cls: type,
    change_log_entity_type: str,
    entity_id: str,
    task_id: str,
) -> dict[str, Any]:
    outcome = asyncio.run(
        _async_run(entity_type, orm_cls, change_log_entity_type, entity_id, task_id)
    )
    return _shape(outcome, entity_id)


@celery_app.task(name="metaprofile.enrich.tech", bind=True)
def enrich_tech(self, tech_id: str) -> dict[str, Any]:
    logger.info("enrich_tech_start", tech_id=tech_id)
    return _run(EntityType.TECH, TechProfileORM, "tech", tech_id, self.request.id)


@celery_app.task(name="metaprofile.enrich.project", bind=True)
def enrich_project(self, project_id: str) -> dict[str, Any]:
    logger.info("enrich_project_start", project_id=project_id)
    return _run(EntityType.PROJECT, ProjectProfileORM, "project", project_id, self.request.id)


@celery_app.task(name="metaprofile.enrich.org", bind=True)
def enrich_org(self, org_id: str) -> dict[str, Any]:
    logger.info("enrich_org_start", org_id=org_id)
    return _run(EntityType.ORG, OrgProfileORM, "org", org_id, self.request.id)


@celery_app.task(name="metaprofile.enrich.person", bind=True)
def enrich_person(self, person_id: str) -> dict[str, Any]:
    logger.info("enrich_person_start", person_id=person_id)
    return _run(EntityType.PERSON, PersonProfileORM, "person", person_id, self.request.id)


# 触发器按 profile_type 取任务
ENRICH_TASKS: dict[str, Any] = {
    "tech": enrich_tech,
    "project": enrich_project,
    "org": enrich_org,
    "person": enrich_person,
}
