"""人员画像查询服务。"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from metaprofile.profile_person.domain.orm_models import (
    EntityChangeLogORM,
    PersonFocusORM,
    PersonProfileORM,
)
from metaprofile.profile_person.schemas.request import (
    SearchRequest,
    SemanticSearchRequest,
)
from metaprofile.profile_person.schemas.response import (
    ChangeRecord,
    ChangeRecordList,
    PersonProfileResponse,
    PersonSearchResultItem,
    PersonSearchResultList,
)
from metaprofile.shared.db.elasticsearch import ESRepo
from metaprofile.shared.llm.embedding import get_default_embedding_client
from metaprofile.shared.schemas.base import ReviewType
from metaprofile.shared.schemas.entity_person import (
    AcademicForm,
    AuthorRank,
    Degree,
    Gender,
    PersonAcademicOutput,
    PersonAward,
    PersonCareer,
    PersonCategory,
    PersonEducation,
    PersonFocus,
    PersonOpinion,
    PersonReformFocus,
    PersonReview,
)

logger = structlog.get_logger(__name__)

_ES_INDEX = "person_profile"

EAGER_OPTIONS = [
    selectinload(PersonProfileORM.educations),
    selectinload(PersonProfileORM.careers),
    selectinload(PersonProfileORM.awards),
    selectinload(PersonProfileORM.academic_outputs),
    selectinload(PersonProfileORM.opinions),
    selectinload(PersonProfileORM.reviews),
    selectinload(PersonProfileORM.tech_focuses),
    selectinload(PersonProfileORM.reform_focuses),
]


def orm_to_response(orm: PersonProfileORM) -> PersonProfileResponse:
    tech_focuses = [
        f for f in (orm.tech_focuses or []) if f.focus_type == "tech"
    ]
    reform_focuses = [
        f for f in (orm.reform_focuses or []) if f.focus_type == "reform"
    ]

    return PersonProfileResponse(
        person_id=orm.person_id,
        name_cn=orm.name_cn,
        name_en=orm.name_en,
        gender=Gender(orm.gender),
        avatar=orm.avatar,
        nationality=orm.nationality,
        summary=orm.summary,
        birth_date=orm.birth_date,
        age=orm.age,
        birthplace=orm.birthplace,
        ethnicity=orm.ethnicity,
        current_residence=orm.current_residence,
        current_org=orm.current_org,
        current_enterprise=orm.current_enterprise,
        current_military_unit=orm.current_military_unit,
        current_position=orm.current_position,
        highest_degree=Degree(orm.highest_degree) if orm.highest_degree else None,
        person_category=PersonCategory(orm.person_category) if orm.person_category else None,
        professional_domains=orm.professional_domains,
        professional_skills=orm.professional_skills,
        social_media=orm.social_media,
        personality_traits=orm.personality_traits,
        hobbies=orm.hobbies,
        management_philosophy=orm.management_philosophy,
        remark=orm.remark,
        confidence=orm.confidence,
        educations=[
            PersonEducation(
                start_date=e.start_date,
                degree_date=e.degree_date,
                degree=Degree(e.degree) if e.degree else None,
                school=e.school,
                major=e.major,
            )
            for e in orm.educations
        ],
        careers=[
            PersonCareer(
                start_date=c.start_date,
                end_date=c.end_date,
                org=c.org,
                enterprise=c.enterprise,
                military_unit=c.military_unit,
                position=c.position,
            )
            for c in orm.careers
        ],
        awards=[PersonAward(description=a.description) for a in orm.awards],
        academic_outputs=[
            PersonAcademicOutput(
                name=a.name,
                form=AcademicForm(a.form) if a.form else None,
                publish_date=a.publish_date,
                rank=AuthorRank(a.rank) if a.rank else None,
                tech_domain=a.tech_domain,
                collaborators=a.collaborators,
                citations=a.citations,
                is_representative=a.is_representative,
            )
            for a in orm.academic_outputs
        ],
        opinions=[
            PersonOpinion(
                title=o.title,
                publish_date=o.publish_date,
                raw_text=o.raw_text,
                occasion=o.occasion,
                main_points=o.main_points,
                target_keywords=o.target_keywords,
            )
            for o in orm.opinions
        ],
        reviews=[
            PersonReview(
                content=r.content,
                review_org=r.review_org,
                review_enterprise=r.review_enterprise,
                review_person=r.review_person,
                review_type=ReviewType(r.review_type) if r.review_type else None,
                review_date=r.review_date,
            )
            for r in orm.reviews
        ],
        tech_focuses=[
            PersonFocus(
                content=f.content,
                consistency_with_policy=f.consistency_with_policy,
                potential_impact=f.potential_impact,
            )
            for f in tech_focuses
        ],
        reform_focuses=[
            PersonReformFocus(
                content=f.content,
                consistency_with_policy=f.consistency_with_policy,
                potential_impact=f.potential_impact,
            )
            for f in reform_focuses
        ],
    )


class PersonQueryService:
    """人员画像查询服务。"""

    def __init__(self) -> None:
        self._es = ESRepo()

    async def get_by_id(
        self, session: AsyncSession, person_id: str
    ) -> PersonProfileResponse | None:
        stmt = (
            select(PersonProfileORM)
            .where(PersonProfileORM.person_id == person_id)
            .options(*EAGER_OPTIONS)
        )
        orm = (await session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return orm_to_response(orm)

    async def search(
        self, session: AsyncSession, payload: SearchRequest
    ) -> PersonSearchResultList:
        conditions = []
        if payload.keyword:
            kw = f"%{payload.keyword}%"
            conditions.append(
                or_(
                    PersonProfileORM.name_cn.ilike(kw),
                    PersonProfileORM.name_en.ilike(kw),
                    PersonProfileORM.summary.ilike(kw),
                )
            )
        if payload.person_domain:
            conditions.append(
                or_(
                    *[
                        cast(PersonProfileORM.professional_domains, JSONB).contains([d])
                        for d in payload.person_domain
                    ]
                )
            )
        if payload.invention_date_from:
            conditions.append(PersonProfileORM.birth_date >= payload.invention_date_from)
        if payload.invention_date_to:
            conditions.append(PersonProfileORM.birth_date <= payload.invention_date_to)

        base_q = select(PersonProfileORM)
        if conditions:
            base_q = base_q.where(and_(*conditions))

        total: int = (
            await session.execute(
                select(func.count()).select_from(base_q.subquery())
            )
        ).scalar_one()

        offset = (payload.page - 1) * payload.page_size
        rows = (
            await session.execute(base_q.offset(offset).limit(payload.page_size))
        ).scalars().all()

        items = [
            PersonSearchResultItem(
                person_id=r.person_id,
                person_name_cn=r.name_cn,
                person_domain=r.professional_domains,
            )
            for r in rows
        ]
        return PersonSearchResultList(items=items, total=total)

    async def semantic_search(
        self, payload: SemanticSearchRequest
    ) -> PersonSearchResultList:
        vector = await get_default_embedding_client().embed_one(payload.query)

        filter_query = None
        if payload.person_domain_filter:
            filter_query = {
                "bool": {
                    "should": [
                        {"term": {"professional_domains": d}}
                        for d in payload.person_domain_filter
                    ],
                    "minimum_should_match": 1,
                }
            }

        hits = await self._es.knn_search(
            index_alias=_ES_INDEX,
            vector=vector,
            top_k=payload.top_k,
            filter_query=filter_query,
        )
        items = [
            PersonSearchResultItem(
                person_id=h.get("entity_id", h.get("_id", "")),
                person_name_cn=h.get("name_cn", ""),
                person_domain=h.get("professional_domains", []),
                relevance_score=h.get("_score"),
            )
            for h in hits
        ]
        return PersonSearchResultList(items=items, total=len(items))

    async def batch_get(
        self, session: AsyncSession, person_ids: list[str]
    ) -> list[PersonProfileResponse]:
        stmt = (
            select(PersonProfileORM)
            .where(PersonProfileORM.person_id.in_(person_ids))
            .options(*EAGER_OPTIONS)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [orm_to_response(r) for r in rows]

    async def list_changes(
        self,
        session: AsyncSession,
        *,
        since: datetime,
        until: datetime | None,
        limit: int,
    ) -> ChangeRecordList:
        conditions = [
            EntityChangeLogORM.entity_type == "person",
            EntityChangeLogORM.changed_at >= since,
        ]
        if until:
            conditions.append(EntityChangeLogORM.changed_at <= until)

        where_clause = and_(*conditions)
        total: int = (
            await session.execute(
                select(func.count()).select_from(
                    select(EntityChangeLogORM).where(where_clause).subquery()
                )
            )
        ).scalar_one()

        rows = (
            await session.execute(
                select(EntityChangeLogORM)
                .where(where_clause)
                .order_by(EntityChangeLogORM.changed_at.desc())
                .limit(limit)
            )
        ).scalars().all()

        items = [
            ChangeRecord(
                person_id=r.entity_id,
                field=r.field,
                old_value=r.old_value,
                new_value=r.new_value,
                method=r.method,
                operator=r.operator,
                changed_at=r.changed_at,
            )
            for r in rows
        ]
        return ChangeRecordList(items=items, total=total)
