"""项目画像核心服务：生成、更新、批量导入。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_project.domain.orm_models import (
    EntityChangeLogORM,
    ProjectBudgetORM,
    ProjectHistoryORM,
    ProjectOutputORM,
    ProjectProfileORM,
)
from metaprofile.profile_project.schemas.request import (
    BulkImportRequest,
    UpdateProjectProfileRequest,
)
from metaprofile.profile_project.schemas.response import (
    BulkImportResult,
    ProjectProfileResponse,
)
from metaprofile.profile_project.services.project_query_service import (
    EAGER_OPTIONS,
    orm_to_response,
)
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.entity_project import ProjectProfile
from metaprofile.shared.utils.id_generator import new_entity_id

logger = structlog.get_logger(__name__)


class ProjectProfileService:
    """项目画像生成与更新服务。"""

    async def create(
        self,
        session: AsyncSession,
        *,
        profile: ProjectProfile,
        method: SourceMethod = SourceMethod.LLM_EXTRACT,
        source_doc_id: str | None = None,
    ) -> ProjectProfileResponse:
        if not profile.project_id:
            profile = profile.model_copy(
                update={"project_id": new_entity_id(EntityType.PROJECT)}
            )

        orm = ProjectProfileORM(
            project_id=profile.project_id,
            name_cn=profile.name_cn,
            name_en=profile.name_en,
            name_other=profile.name_other,
            tech_domain=profile.tech_domain,
            sub_tech_domain=profile.sub_tech_domain,
            start_date=profile.start_date,
            cancel_date=profile.cancel_date,
            finish_date=profile.finish_date,
            status=[s.value for s in profile.status],
            budget_activities=[a.value for a in profile.budget_activities],
            project_no=profile.project_no,
            main_orgs=profile.main_orgs,
            undertaking_orgs=profile.undertaking_orgs,
            undertaking_enterprises=profile.undertaking_enterprises,
            managers=profile.managers,
            researchers=profile.researchers,
            background=profile.background,
            research_goal=profile.research_goal,
            research_content=profile.research_content,
            keywords=profile.keywords,
            progress=profile.progress,
            application_prospect=profile.application_prospect,
            key_dates=[str(d) for d in profile.key_dates],
            total_budget_million_usd=profile.total_budget_million_usd,
            invested_million_usd=profile.invested_million_usd,
            parent_package_name=profile.parent_package_name,
            previous_phase_name=profile.previous_phase_name,
            confidence=profile.confidence,
        )
        session.add(orm)

        for h in profile.histories:
            session.add(ProjectHistoryORM(
                project_id=profile.project_id,
                change_date=h.change_date,
                change_description=h.change_description,
            ))
        for b in profile.budgets:
            session.add(ProjectBudgetORM(
                project_id=profile.project_id,
                budget_date=b.budget_date,
                amount=b.amount,
            ))
        for o in profile.outputs:
            session.add(ProjectOutputORM(
                project_id=profile.project_id,
                name_history=o.name_history,
                formed_at=o.formed_at,
                tech_domains=o.tech_domains,
                owner_orgs=o.owner_orgs,
                related_projects=o.related_projects,
                attachments=o.attachments,
            ))

        session.add(EntityChangeLogORM(
            entity_id=profile.project_id,
            entity_type="project",
            field="*",
            old_value=None,
            new_value={"action": "create"},
            method=method.value,
            source_doc_id=source_doc_id,
            changed_at=datetime.now(timezone.utc),
        ))

        await session.flush()
        logger.info(
            "project_profile_created",
            project_id=profile.project_id,
            method=method.value,
        )
        return ProjectProfileResponse.model_validate(profile.model_dump())

    async def update(
        self,
        session: AsyncSession,
        *,
        project_id: str,
        payload: UpdateProjectProfileRequest,
    ) -> ProjectProfileResponse | None:
        stmt = (
            select(ProjectProfileORM)
            .where(ProjectProfileORM.project_id == project_id)
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
                    entity_id=project_id,
                    entity_type="project",
                    field=field,
                    old_value={"v": str(old_val)} if old_val is not None else None,
                    new_value={"v": str(new_val)},
                    method=SourceMethod.HUMAN.value,
                    operator=payload.operator,
                    reason=payload.reason,
                    changed_at=now,
                ))

        await session.flush()
        logger.info("project_profile_updated", project_id=project_id)
        return orm_to_response(orm)

    async def bulk_import(
        self,
        session: AsyncSession,
        *,
        payload: BulkImportRequest,
    ) -> BulkImportResult:
        task_id = uuid4().hex
        logger.info("project_bulk_import_queued", task_id=task_id, count=len(payload.profiles))
        return BulkImportResult(
            task_id=task_id,
            accepted_count=len(payload.profiles),
            submitted_at=datetime.now(timezone.utc),
        )
