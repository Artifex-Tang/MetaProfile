"""enrich celery 任务：4 画像共享，包裹 shared/enrich/orm_enricher 核心。

任务（同步 celery 任务体内用 asyncio.run 跑异步补全核心）：
- enrich_tech(tech_id) / enrich_project(project_id) / enrich_org(org_id) / enrich_person(person_id)

每个任务：开 session → 调 orm_enricher.enrich_one（直写 typed ORM）→ 返回结果 dict。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from metaprofile.foundation.enrichment.llm_filler import LLMFieldFiller
from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_person.domain.orm_models import PersonProfileORM
from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.enrich.orm_enricher import EnrichOutcome, enrich_one
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


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


async def _async_run(
    entity_type: EntityType,
    orm_cls: type,
    change_log_entity_type: str,
    entity_id: str,
) -> EnrichOutcome:
    async with get_session() as session:
        return await enrich_one(
            session=session,
            entity_type=entity_type,
            orm_cls=orm_cls,
            entity_id=entity_id,
            filler=LLMFieldFiller(LLMGateway()),
            change_log_entity_type=change_log_entity_type,
        )


def _run(
    entity_type: EntityType,
    orm_cls: type,
    change_log_entity_type: str,
    entity_id: str,
) -> dict[str, Any]:
    outcome = asyncio.run(
        _async_run(entity_type, orm_cls, change_log_entity_type, entity_id)
    )
    return _shape(outcome, entity_id)


@celery_app.task(name="metaprofile.enrich.tech")
def enrich_tech(tech_id: str) -> dict[str, Any]:
    logger.info("enrich_tech_start", tech_id=tech_id)
    return _run(EntityType.TECH, TechProfileORM, "tech", tech_id)


@celery_app.task(name="metaprofile.enrich.project")
def enrich_project(project_id: str) -> dict[str, Any]:
    logger.info("enrich_project_start", project_id=project_id)
    return _run(EntityType.PROJECT, ProjectProfileORM, "project", project_id)


@celery_app.task(name="metaprofile.enrich.org")
def enrich_org(org_id: str) -> dict[str, Any]:
    logger.info("enrich_org_start", org_id=org_id)
    return _run(EntityType.ORG, OrgProfileORM, "org", org_id)


@celery_app.task(name="metaprofile.enrich.person")
def enrich_person(person_id: str) -> dict[str, Any]:
    logger.info("enrich_person_start", person_id=person_id)
    return _run(EntityType.PERSON, PersonProfileORM, "person", person_id)


# 触发器按 profile_type 取任务
ENRICH_TASKS: dict[str, Any] = {
    "tech": enrich_tech,
    "project": enrich_project,
    "org": enrich_org,
    "person": enrich_person,
}
