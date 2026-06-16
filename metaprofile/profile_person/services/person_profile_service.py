"""人员画像核心服务：生成、更新、批量导入。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_person.domain.orm_models import (
    EntityChangeLogORM,
    PersonAcademicOutputORM,
    PersonAwardORM,
    PersonCareerORM,
    PersonEducationORM,
    PersonFocusORM,
    PersonOpinionORM,
    PersonProfileORM,
    PersonReviewORM,
)
from metaprofile.profile_person.schemas.request import (
    BulkImportRequest,
    UpdatePersonProfileRequest,
)
from metaprofile.profile_person.schemas.response import (
    BulkImportResult,
    PersonProfileResponse,
)
from metaprofile.profile_person.services.person_query_service import (
    EAGER_OPTIONS,
    orm_to_response,
)
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.entity_person import PersonProfile
from metaprofile.shared.utils.id_generator import new_entity_id

logger = structlog.get_logger(__name__)


class PersonProfileService:
    """人员画像生成与更新服务。"""

    async def create(
        self,
        session: AsyncSession,
        *,
        profile: PersonProfile,
        method: SourceMethod = SourceMethod.LLM_EXTRACT,
        source_doc_id: str | None = None,
    ) -> PersonProfileResponse:
        if not profile.person_id:
            profile = profile.model_copy(
                update={"person_id": new_entity_id(EntityType.PERSON)}
            )

        orm = PersonProfileORM(
            person_id=profile.person_id,
            name_cn=profile.name_cn,
            name_en=profile.name_en,
            gender=profile.gender.value,
            avatar=profile.avatar,
            nationality=profile.nationality,
            summary=profile.summary,
            birth_date=profile.birth_date,
            age=profile.age,
            birthplace=profile.birthplace,
            ethnicity=profile.ethnicity,
            current_residence=profile.current_residence,
            current_org=profile.current_org,
            current_enterprise=profile.current_enterprise,
            current_military_unit=profile.current_military_unit,
            current_position=profile.current_position,
            highest_degree=profile.highest_degree.value if profile.highest_degree else None,
            person_category=profile.person_category.value if profile.person_category else None,
            professional_domains=profile.professional_domains,
            professional_skills=profile.professional_skills,
            social_media=profile.social_media,
            personality_traits=profile.personality_traits,
            hobbies=profile.hobbies,
            management_philosophy=profile.management_philosophy,
            remark=profile.remark,
            confidence=profile.confidence,
        )
        session.add(orm)

        for e in profile.educations:
            session.add(PersonEducationORM(
                person_id=profile.person_id,
                start_date=e.start_date,
                degree_date=e.degree_date,
                degree=e.degree.value if e.degree else None,
                school=e.school,
                major=e.major,
            ))
        for c in profile.careers:
            session.add(PersonCareerORM(
                person_id=profile.person_id,
                start_date=c.start_date,
                end_date=c.end_date,
                org=c.org,
                enterprise=c.enterprise,
                military_unit=c.military_unit,
                position=c.position,
            ))
        for a in profile.awards:
            session.add(PersonAwardORM(
                person_id=profile.person_id,
                description=a.description,
            ))
        for a in profile.academic_outputs:
            session.add(PersonAcademicOutputORM(
                person_id=profile.person_id,
                name=a.name,
                form=a.form.value if a.form else None,
                publish_date=a.publish_date,
                rank=a.rank.value if a.rank else None,
                tech_domain=a.tech_domain,
                collaborators=a.collaborators,
                citations=a.citations,
                is_representative=a.is_representative,
            ))
        for o in profile.opinions:
            session.add(PersonOpinionORM(
                person_id=profile.person_id,
                title=o.title,
                publish_date=o.publish_date,
                raw_text=o.raw_text,
                occasion=o.occasion,
                main_points=o.main_points,
                target_keywords=o.target_keywords,
            ))
        for r in profile.reviews:
            session.add(PersonReviewORM(
                person_id=profile.person_id,
                content=r.content,
                review_org=r.review_org,
                review_enterprise=r.review_enterprise,
                review_person=r.review_person,
                review_type=r.review_type.value if r.review_type else None,
                review_date=r.review_date,
            ))
        for f in profile.tech_focuses:
            session.add(PersonFocusORM(
                person_id=profile.person_id,
                focus_type="tech",
                content=f.content,
                consistency_with_policy=f.consistency_with_policy,
                potential_impact=f.potential_impact,
            ))
        for f in profile.reform_focuses:
            session.add(PersonFocusORM(
                person_id=profile.person_id,
                focus_type="reform",
                content=f.content,
                consistency_with_policy=f.consistency_with_policy,
                potential_impact=f.potential_impact,
            ))

        session.add(EntityChangeLogORM(
            entity_id=profile.person_id,
            entity_type="person",
            field="*",
            old_value=None,
            new_value={"action": "create"},
            method=method.value,
            source_doc_id=source_doc_id,
            changed_at=datetime.now(timezone.utc),
        ))

        await session.flush()
        logger.info(
            "person_profile_created",
            person_id=profile.person_id,
            method=method.value,
        )
        return PersonProfileResponse.model_validate(profile.model_dump())

    async def update(
        self,
        session: AsyncSession,
        *,
        person_id: str,
        payload: UpdatePersonProfileRequest,
    ) -> PersonProfileResponse | None:
        stmt = (
            select(PersonProfileORM)
            .where(PersonProfileORM.person_id == person_id)
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
                    entity_id=person_id,
                    entity_type="person",
                    field=field,
                    old_value={"v": str(old_val)} if old_val is not None else None,
                    new_value={"v": str(new_val)},
                    method=SourceMethod.HUMAN.value,
                    operator=payload.operator,
                    reason=payload.reason,
                    changed_at=now,
                ))

        await session.flush()
        logger.info("person_profile_updated", person_id=person_id)
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
                logger.warning("person_bulk_import_item_failed", error=str(exc))
        await session.commit()
        logger.info("person_bulk_import_done", task_id=task_id, count=accepted)
        return BulkImportResult(
            task_id=task_id,
            accepted_count=accepted,
            submitted_at=datetime.now(timezone.utc),
        )
