"""机构画像查询服务。"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from metaprofile.profile_org.domain.orm_models import (
    EntityChangeLogORM,
    OrgProfileORM,
)
from metaprofile.profile_org.schemas.request import (
    SearchRequest,
    SemanticSearchRequest,
)
from metaprofile.profile_org.schemas.response import (
    ChangeRecord,
    ChangeRecordList,
    OrgProfileResponse,
    OrgSearchResultItem,
    OrgSearchResultList,
)
from metaprofile.shared.db.elasticsearch import ESRepo
from metaprofile.shared.llm.embedding import get_default_embedding_client
from metaprofile.shared.schemas.entity_org import (
    OrgActivity,
    OrgAddress,
    OrgAffiliation,
    OrgAward,
    OrgBudget,
    OrgFacility,
    OrgFundingReceived,
    OrgHistory,
    OrgNature,
    OrgOutput,
    OrgReview,
    OrgTeam,
    OrgType,
)
from metaprofile.shared.schemas.base import ReviewType

logger = structlog.get_logger(__name__)

_ES_INDEX = "org_profile"

EAGER_OPTIONS = [
    selectinload(OrgProfileORM.histories),
    selectinload(OrgProfileORM.affiliations),
    selectinload(OrgProfileORM.awards),
    selectinload(OrgProfileORM.budgets),
    selectinload(OrgProfileORM.fundings_received),
    selectinload(OrgProfileORM.outputs),
    selectinload(OrgProfileORM.reviews),
    selectinload(OrgProfileORM.addresses),
    selectinload(OrgProfileORM.activities),
    selectinload(OrgProfileORM.team),
    selectinload(OrgProfileORM.facilities),
]


def orm_to_response(orm: OrgProfileORM) -> OrgProfileResponse:
    team = None
    if orm.team:
        team = OrgTeam(
            top_talents=orm.team.top_talents,
            award_winners=orm.team.award_winners,
            team_size=orm.team.team_size,
            talent_type=orm.team.talent_type,
        )

    return OrgProfileResponse(
        org_id=orm.org_id,
        name_cn=orm.name_cn,
        name_en=orm.name_en,
        name_other=orm.name_other,
        country=orm.country,
        founded_date=orm.founded_date,
        dissolved_date=orm.dissolved_date,
        operating_years=orm.operating_years,
        website=orm.website,
        summary=orm.summary,
        org_types=[OrgType(t) for t in orm.org_types],
        nature=OrgNature(orm.nature),
        function=orm.function,
        scale=orm.scale,
        tech_domains=orm.tech_domains,
        predecessor_names=orm.predecessor_names,
        departments=orm.departments,
        strategic_plans=orm.strategic_plans,
        evaluation_report=orm.evaluation_report,
        new_key_projects=orm.new_key_projects,
        remark=orm.remark,
        confidence=orm.confidence,
        histories=[
            OrgHistory(
                change_date=h.change_date,
                change_description=h.change_description,
            )
            for h in orm.histories
        ],
        affiliations=[
            OrgAffiliation(change_date=a.change_date, parent_name=a.parent_name)
            for a in orm.affiliations
        ],
        awards=[
            OrgAward(
                description=a.description,
                name=a.name,
                reason=a.reason,
                award_date=a.award_date,
                level=a.level,
                award_type=a.award_type,
            )
            for a in orm.awards
        ],
        budgets=[
            OrgBudget(
                funder_name=b.funder_name,
                budget_date=b.budget_date,
                amount_usd=float(b.amount_usd) if b.amount_usd is not None else None,
            )
            for b in orm.budgets
        ],
        fundings_received=[
            OrgFundingReceived(
                funder_name=f.funder_name,
                fund_date=f.fund_date,
                amount_or_equipment=f.amount_or_equipment,
            )
            for f in orm.fundings_received
        ],
        outputs=[
            OrgOutput(
                name=o.name,
                form=o.form,
                author=o.author,
                publish_date=o.publish_date,
                attachment=o.attachment,
            )
            for o in orm.outputs
        ],
        reviews=[
            OrgReview(
                content=r.content,
                review_org=r.review_org,
                review_person=r.review_person,
                review_type=ReviewType(r.review_type) if r.review_type else None,
                review_date=r.review_date,
            )
            for r in orm.reviews
        ],
        addresses=[
            OrgAddress(
                address=a.address,
                longitude=a.longitude,
                latitude=a.latitude,
            )
            for a in orm.addresses
        ],
        activities=[
            OrgActivity(
                activity_type=a.activity_type,
                content=a.content,
                activity_date=a.activity_date,
                locations=a.locations,
            )
            for a in orm.activities
        ],
        team=team,
        facilities=[
            OrgFacility(
                name=f.name,
                purpose=f.purpose,
                experiment_status=f.experiment_status,
                launch_date=f.launch_date,
                construction_cost_wan_usd=float(f.construction_cost_wan_usd)
                if f.construction_cost_wan_usd is not None
                else None,
            )
            for f in orm.facilities
        ],
    )


class OrgQueryService:
    """机构画像查询服务。"""

    def __init__(self) -> None:
        self._es = ESRepo()

    async def get_by_id(
        self, session: AsyncSession, org_id: str
    ) -> OrgProfileResponse | None:
        stmt = (
            select(OrgProfileORM)
            .where(OrgProfileORM.org_id == org_id)
            .options(*EAGER_OPTIONS)
        )
        orm = (await session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return orm_to_response(orm)

    async def search(
        self, session: AsyncSession, payload: SearchRequest
    ) -> OrgSearchResultList:
        conditions = []
        if payload.keyword:
            kw = f"%{payload.keyword}%"
            conditions.append(
                or_(
                    OrgProfileORM.name_cn.ilike(kw),
                    OrgProfileORM.name_en.ilike(kw),
                    OrgProfileORM.summary.ilike(kw),
                )
            )
        if payload.org_domain:
            conditions.append(
                or_(
                    *[
                        cast(OrgProfileORM.tech_domains, JSONB).contains([d])
                        for d in payload.org_domain
                    ]
                )
            )
        if payload.invention_date_from:
            conditions.append(OrgProfileORM.founded_date >= payload.invention_date_from)
        if payload.invention_date_to:
            conditions.append(OrgProfileORM.founded_date <= payload.invention_date_to)

        base_q = select(OrgProfileORM)
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
            OrgSearchResultItem(
                org_id=r.org_id,
                org_name_cn=r.name_cn,
                org_domain=r.tech_domains,
            )
            for r in rows
        ]
        return OrgSearchResultList(items=items, total=total)

    async def semantic_search(
        self, payload: SemanticSearchRequest
    ) -> OrgSearchResultList:
        vector = await get_default_embedding_client().embed_one(payload.query)

        filter_query = None
        if payload.org_domain_filter:
            filter_query = {
                "bool": {
                    "should": [
                        {"term": {"tech_domains": d}}
                        for d in payload.org_domain_filter
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
            OrgSearchResultItem(
                org_id=h.get("entity_id", h.get("_id", "")),
                org_name_cn=h.get("name_cn", ""),
                org_domain=h.get("tech_domains", []),
                relevance_score=h.get("_score"),
            )
            for h in hits
        ]
        return OrgSearchResultList(items=items, total=len(items))

    async def batch_get(
        self, session: AsyncSession, org_ids: list[str]
    ) -> list[OrgProfileResponse]:
        stmt = (
            select(OrgProfileORM)
            .where(OrgProfileORM.org_id.in_(org_ids))
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
            EntityChangeLogORM.entity_type == "org",
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
                org_id=r.entity_id,
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
