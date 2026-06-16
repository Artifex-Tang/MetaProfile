"""
技术画像核心服务：生成、更新、批量导入。

业务规则：
1. 字段级更新：仅更新 payload 中显式给出的字段，其他字段保持。
2. 每次更新写一条 entity_change_log（旧值/新值/抽取方式/操作者）。
3. 关系字段（贡献者、被评议）通过 foundation/relation 模块异步同步到 Neo4j。
4. ES 与 PostgreSQL 通过 outbox 模式保证最终一致。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_tech.domain.orm_models import (
    EntityChangeLogORM,
    TechAcademicOutputORM,
    TechDevMilestoneORM,
    TechExperimentORM,
    TechFundingORM,
    TechProfileORM,
    TechReviewImpactORM,
)
from metaprofile.profile_tech.schemas.request import (
    BulkImportRequest,
    UpdateTechProfileRequest,
)
from metaprofile.profile_tech.schemas.response import (
    BulkImportResult,
    TechProfileResponse,
)
from metaprofile.profile_tech.services.tech_query_service import (
    EAGER_OPTIONS,
    orm_to_response,
)
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.entity_tech import TechProfile
from metaprofile.shared.utils.id_generator import new_entity_id

logger = structlog.get_logger(__name__)


class TechProfileService:
    """技术画像生成与更新服务。"""

    async def create(
        self,
        session: AsyncSession,
        *,
        profile: TechProfile,
        method: SourceMethod = SourceMethod.LLM_EXTRACT,
        source_doc_id: str | None = None,
    ) -> TechProfileResponse:
        if not profile.tech_id:
            profile = profile.model_copy(
                update={"tech_id": new_entity_id(EntityType.TECH)}
            )

        orm = TechProfileORM(
            tech_id=profile.tech_id,
            tech_name_cn=profile.tech_name_cn,
            tech_name_en=profile.tech_name_en,
            tech_name_other=profile.tech_name_other,
            tech_domain=profile.tech_domain,
            invention_date=profile.invention_date,
            application_date=profile.application_date,
            tech_summary=profile.tech_summary,
            dev_goal=profile.dev_goal,
            project_layout=profile.project_layout,
            key_points=profile.key_points,
            transformation_status=profile.transformation_status,
            basic_research_status=profile.basic_research_status,
            autonomy_capability=profile.autonomy_capability,
            industrial_capability=profile.industrial_capability,
            tech_advantages=profile.tech_advantages,
            current_status=profile.current_status,
            trend=profile.trend,
            remark=profile.remark,
            confidence=profile.confidence,
        )
        session.add(orm)

        for m in profile.dev_milestones:
            session.add(TechDevMilestoneORM(
                tech_id=profile.tech_id,
                milestone_date=m.milestone_date,
                milestone_name=m.milestone_name,
                contributor_keywords=m.contributor_keywords,
                milestone_content=m.milestone_content,
            ))
        for m in profile.review_impacts:
            session.add(TechReviewImpactORM(
                tech_id=profile.tech_id,
                review_date=m.review_date,
                review_org=m.review_org,
                review_person=m.review_person,
                review_content=m.review_content,
                review_type=m.review_type.value if m.review_type else None,
            ))
        for m in profile.funding:
            session.add(TechFundingORM(
                tech_id=profile.tech_id,
                amount=m.amount,
                source=m.source,
            ))
        for m in profile.academic_outputs:
            session.add(TechAcademicOutputORM(
                tech_id=profile.tech_id,
                name=m.name,
                publish_date=m.publish_date,
                subject_keywords=m.subject_keywords,
                image=m.image,
            ))
        for m in profile.experiments:
            session.add(TechExperimentORM(
                tech_id=profile.tech_id,
                content=m.content,
                experiment_date=m.experiment_date,
                result=m.result,
                subject_keywords=m.subject_keywords,
                image=m.image,
            ))

        session.add(EntityChangeLogORM(
            entity_id=profile.tech_id,
            entity_type="tech",
            field="*",
            old_value=None,
            new_value={"action": "create"},
            method=method.value,
            source_doc_id=source_doc_id,
            changed_at=datetime.now(timezone.utc),
        ))

        await session.flush()
        logger.info(
            "tech_profile_created",
            tech_id=profile.tech_id,
            method=method.value,
            source_doc_id=source_doc_id,
        )
        return TechProfileResponse.model_validate(profile.model_dump())

    async def update(
        self,
        session: AsyncSession,
        *,
        tech_id: str,
        payload: UpdateTechProfileRequest,
    ) -> TechProfileResponse | None:
        stmt = (
            select(TechProfileORM)
            .where(TechProfileORM.tech_id == tech_id)
            .options(*EAGER_OPTIONS)
        )
        orm = (await session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None

        updatable = payload.model_dump(
            exclude={"operator", "reason"}, exclude_none=True
        )
        now = datetime.now(timezone.utc)

        for field, new_val in updatable.items():
            old_val = getattr(orm, field, None)
            if old_val != new_val:
                setattr(orm, field, new_val)
                session.add(EntityChangeLogORM(
                    entity_id=tech_id,
                    entity_type="tech",
                    field=field,
                    old_value={"v": str(old_val)} if old_val is not None else None,
                    new_value={"v": str(new_val)},
                    method=SourceMethod.HUMAN.value,
                    operator=payload.operator,
                    reason=payload.reason,
                    changed_at=now,
                ))

        await session.flush()
        logger.info("tech_profile_updated", tech_id=tech_id)
        return orm_to_response(orm)

    async def bulk_import(
        self,
        session: AsyncSession,
        *,
        payload: BulkImportRequest,
    ) -> BulkImportResult:
        task_id = uuid4().hex
        accepted = 0
        for profile in payload.profiles:
            try:
                await self.create(session, profile=profile)
                accepted += 1
            except Exception as exc:
                await session.rollback()
                logger.warning("bulk_import_item_failed", error=str(exc))
        await session.commit()
        logger.info("bulk_import_done", task_id=task_id, count=accepted)
        return BulkImportResult(
            task_id=task_id,
            accepted_count=accepted,
            submitted_at=datetime.now(timezone.utc),
        )
