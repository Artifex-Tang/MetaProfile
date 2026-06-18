"""技术画像查询服务。"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from metaprofile.profile_tech.domain.orm_models import (
    EntityChangeLogORM,
    TechProfileORM,
)
from metaprofile.profile_tech.schemas.request import (
    SearchRequest,
    SemanticSearchRequest,
)
from metaprofile.profile_tech.schemas.response import (
    ChangeRecord,
    ChangeRecordList,
    TechProfileResponse,
    TechSearchResultItem,
    TechSearchResultList,
)
from metaprofile.shared.db.elasticsearch import ESRepo
from metaprofile.shared.llm.embedding import get_default_embedding_client
from metaprofile.shared.schemas.entity_tech import (
    TechAcademicOutput,
    TechDevMilestone,
    TechExperiment,
    TechFunding,
    TechReviewImpact,
)

logger = structlog.get_logger(__name__)

_ES_INDEX = "tech_profile"

EAGER_OPTIONS = [
    selectinload(TechProfileORM.dev_milestones),
    selectinload(TechProfileORM.review_impacts),
    selectinload(TechProfileORM.fundings),
    selectinload(TechProfileORM.academic_outputs),
    selectinload(TechProfileORM.experiments),
]


def orm_to_response(orm: TechProfileORM) -> TechProfileResponse:
    return TechProfileResponse(
        tech_id=orm.tech_id,
        tech_name_cn=orm.tech_name_cn,
        tech_name_en=orm.tech_name_en,
        tech_name_other=orm.tech_name_other,
        tech_domain=orm.tech_domain,
        invention_date=orm.invention_date,
        application_date=orm.application_date,
        tech_summary=orm.tech_summary,
        dev_goal=orm.dev_goal,
        project_layout=orm.project_layout,
        key_points=orm.key_points,
        transformation_status=orm.transformation_status,
        basic_research_status=orm.basic_research_status,
        autonomy_capability=orm.autonomy_capability,
        industrial_capability=orm.industrial_capability,
        tech_advantages=orm.tech_advantages,
        current_status=orm.current_status,
        trend=orm.trend,
        remark=orm.remark,
        confidence=orm.confidence,
        veracity_score=orm.veracity_score,
        timeliness_score=orm.timeliness_score,
        data_as_of=orm.data_as_of,
        dev_milestones=[
            TechDevMilestone(
                milestone_date=m.milestone_date,
                milestone_name=m.milestone_name,
                contributor_keywords=m.contributor_keywords,
                milestone_content=m.milestone_content,
            )
            for m in orm.dev_milestones
        ],
        review_impacts=[
            TechReviewImpact(
                review_date=m.review_date,
                review_org=m.review_org,
                review_person=m.review_person,
                review_content=m.review_content,
                review_type=m.review_type,
            )
            for m in orm.review_impacts
        ],
        funding=[
            TechFunding(amount=m.amount, source=m.source)
            for m in orm.fundings
        ],
        academic_outputs=[
            TechAcademicOutput(
                name=m.name,
                publish_date=m.publish_date,
                subject_keywords=m.subject_keywords,
                image=m.image,
            )
            for m in orm.academic_outputs
        ],
        experiments=[
            TechExperiment(
                content=m.content,
                experiment_date=m.experiment_date,
                result=m.result,
                subject_keywords=m.subject_keywords,
                image=m.image,
            )
            for m in orm.experiments
        ],
    )


class TechQueryService:
    """技术画像查询服务。"""

    def __init__(self) -> None:
        self._es = ESRepo()

    async def get_by_id(
        self, session: AsyncSession, tech_id: str
    ) -> TechProfileResponse | None:
        stmt = (
            select(TechProfileORM)
            .where(TechProfileORM.tech_id == tech_id)
            .options(*EAGER_OPTIONS)
        )
        orm = (await session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return orm_to_response(orm)

    async def search(
        self, session: AsyncSession, payload: SearchRequest
    ) -> TechSearchResultList:
        conditions = []
        if payload.keyword:
            kw = f"%{payload.keyword}%"
            conditions.append(
                or_(
                    TechProfileORM.tech_name_cn.ilike(kw),
                    TechProfileORM.tech_name_en.ilike(kw),
                    TechProfileORM.tech_summary.ilike(kw),
                )
            )
        if payload.tech_domain:
            # CAST JSON → JSONB for @> containment operator
            conditions.append(
                or_(
                    *[
                        cast(TechProfileORM.tech_domain, JSONB).contains([d])
                        for d in payload.tech_domain
                    ]
                )
            )
        if payload.invention_date_from:
            conditions.append(
                TechProfileORM.invention_date >= payload.invention_date_from
            )
        if payload.invention_date_to:
            conditions.append(
                TechProfileORM.invention_date <= payload.invention_date_to
            )

        base_q = select(TechProfileORM)
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
            TechSearchResultItem(
                tech_id=r.tech_id,
                tech_name_cn=r.tech_name_cn,
                tech_domain=r.tech_domain,
            )
            for r in rows
        ]
        return TechSearchResultList(items=items, total=total)

    async def semantic_search(
        self, payload: SemanticSearchRequest
    ) -> TechSearchResultList:
        vector = await get_default_embedding_client().embed_one(payload.query)

        filter_query = None
        if payload.tech_domain_filter:
            filter_query = {
                "bool": {
                    "should": [
                        {"term": {"tech_domain": d}}
                        for d in payload.tech_domain_filter
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
            TechSearchResultItem(
                tech_id=h.get("entity_id", h.get("_id", "")),
                tech_name_cn=h.get("tech_name_cn", ""),
                tech_domain=h.get("tech_domain", []),
                relevance_score=h.get("_score"),
            )
            for h in hits
        ]
        return TechSearchResultList(items=items, total=len(items))

    async def batch_get(
        self, session: AsyncSession, tech_ids: list[str]
    ) -> list[TechProfileResponse]:
        stmt = (
            select(TechProfileORM)
            .where(TechProfileORM.tech_id.in_(tech_ids))
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
            EntityChangeLogORM.entity_type == "tech",
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
                tech_id=r.entity_id,
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
