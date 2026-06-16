"""机构画像核心服务：生成、更新、批量导入。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_org.domain.orm_models import (
    EntityChangeLogORM,
    OrgActivityORM,
    OrgAddressORM,
    OrgAffiliationORM,
    OrgAwardORM,
    OrgBudgetORM,
    OrgFacilityORM,
    OrgFundingReceivedORM,
    OrgHistoryORM,
    OrgOutputORM,
    OrgProfileORM,
    OrgReviewORM,
    OrgTeamORM,
)
from metaprofile.profile_org.schemas.request import (
    BulkImportRequest,
    UpdateOrgProfileRequest,
)
from metaprofile.profile_org.schemas.response import (
    BulkImportResult,
    OrgProfileResponse,
)
from metaprofile.profile_org.services.org_query_service import (
    EAGER_OPTIONS,
    orm_to_response,
)
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.entity_org import OrgProfile
from metaprofile.shared.utils.id_generator import new_entity_id

logger = structlog.get_logger(__name__)


class OrgProfileService:
    """机构画像生成与更新服务。"""

    async def create(
        self,
        session: AsyncSession,
        *,
        profile: OrgProfile,
        method: SourceMethod = SourceMethod.LLM_EXTRACT,
        source_doc_id: str | None = None,
    ) -> OrgProfileResponse:
        if not profile.org_id:
            profile = profile.model_copy(
                update={"org_id": new_entity_id(EntityType.ORG)}
            )

        orm = OrgProfileORM(
            org_id=profile.org_id,
            name_cn=profile.name_cn,
            name_en=profile.name_en,
            name_other=profile.name_other,
            country=profile.country,
            founded_date=profile.founded_date,
            dissolved_date=profile.dissolved_date,
            operating_years=profile.operating_years,
            website=profile.website,
            summary=profile.summary,
            org_types=[t.value for t in profile.org_types],
            nature=profile.nature.value,
            function=profile.function,
            scale=profile.scale,
            tech_domains=profile.tech_domains,
            predecessor_names=profile.predecessor_names,
            departments=profile.departments,
            strategic_plans=profile.strategic_plans,
            evaluation_report=profile.evaluation_report,
            new_key_projects=profile.new_key_projects,
            remark=profile.remark,
            confidence=profile.confidence,
        )
        session.add(orm)

        for h in profile.histories:
            session.add(OrgHistoryORM(
                org_id=profile.org_id,
                change_date=h.change_date,
                change_description=h.change_description,
            ))
        for a in profile.affiliations:
            session.add(OrgAffiliationORM(
                org_id=profile.org_id,
                change_date=a.change_date,
                parent_name=a.parent_name,
            ))
        for a in profile.awards:
            session.add(OrgAwardORM(
                org_id=profile.org_id,
                description=a.description,
                name=a.name,
                reason=a.reason,
                award_date=a.award_date,
                level=a.level,
                award_type=a.award_type,
            ))
        for b in profile.budgets:
            session.add(OrgBudgetORM(
                org_id=profile.org_id,
                funder_name=b.funder_name,
                budget_date=b.budget_date,
                amount_usd=b.amount_usd,
            ))
        for f in profile.fundings_received:
            session.add(OrgFundingReceivedORM(
                org_id=profile.org_id,
                funder_name=f.funder_name,
                fund_date=f.fund_date,
                amount_or_equipment=f.amount_or_equipment,
            ))
        for o in profile.outputs:
            session.add(OrgOutputORM(
                org_id=profile.org_id,
                name=o.name,
                form=o.form,
                author=o.author,
                publish_date=o.publish_date,
                attachment=o.attachment,
            ))
        for r in profile.reviews:
            session.add(OrgReviewORM(
                org_id=profile.org_id,
                content=r.content,
                review_org=r.review_org,
                review_person=r.review_person,
                review_type=r.review_type.value if r.review_type else None,
                review_date=r.review_date,
            ))
        for a in profile.addresses:
            session.add(OrgAddressORM(
                org_id=profile.org_id,
                address=a.address,
                longitude=a.longitude,
                latitude=a.latitude,
            ))
        for a in profile.activities:
            session.add(OrgActivityORM(
                org_id=profile.org_id,
                activity_type=a.activity_type,
                content=a.content,
                activity_date=a.activity_date,
                locations=a.locations,
            ))
        if profile.team:
            session.add(OrgTeamORM(
                org_id=profile.org_id,
                top_talents=profile.team.top_talents,
                award_winners=profile.team.award_winners,
                team_size=profile.team.team_size,
                talent_type=profile.team.talent_type,
            ))
        for f in profile.facilities:
            session.add(OrgFacilityORM(
                org_id=profile.org_id,
                name=f.name,
                purpose=f.purpose,
                experiment_status=f.experiment_status,
                launch_date=f.launch_date,
                construction_cost_wan_usd=f.construction_cost_wan_usd,
            ))

        session.add(EntityChangeLogORM(
            entity_id=profile.org_id,
            entity_type="org",
            field="*",
            old_value=None,
            new_value={"action": "create"},
            method=method.value,
            source_doc_id=source_doc_id,
            changed_at=datetime.now(timezone.utc),
        ))

        await session.flush()
        logger.info("org_profile_created", org_id=profile.org_id, method=method.value)
        return OrgProfileResponse.model_validate(profile.model_dump())

    async def update(
        self,
        session: AsyncSession,
        *,
        org_id: str,
        payload: UpdateOrgProfileRequest,
    ) -> OrgProfileResponse | None:
        stmt = (
            select(OrgProfileORM)
            .where(OrgProfileORM.org_id == org_id)
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
                    entity_id=org_id,
                    entity_type="org",
                    field=field,
                    old_value={"v": str(old_val)} if old_val is not None else None,
                    new_value={"v": str(new_val)},
                    method=SourceMethod.HUMAN.value,
                    operator=payload.operator,
                    reason=payload.reason,
                    changed_at=now,
                ))

        await session.flush()
        logger.info("org_profile_updated", org_id=org_id)
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
                logger.warning("org_bulk_import_item_failed", error=str(exc))
        await session.commit()
        logger.info("org_bulk_import_done", task_id=task_id, count=accepted)
        return BulkImportResult(
            task_id=task_id,
            accepted_count=accepted,
            submitted_at=datetime.now(timezone.utc),
        )
