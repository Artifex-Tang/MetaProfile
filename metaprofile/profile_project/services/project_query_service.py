"""项目画像查询服务。"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import Text, and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from metaprofile.profile_project.domain.orm_models import (
    EntityChangeLogORM,
    ProjectProfileORM,
)
from metaprofile.profile_project.schemas.request import (
    SearchRequest,
    SemanticSearchRequest,
)
from metaprofile.profile_project.schemas.response import (
    ChangeRecord,
    ChangeRecordList,
    ProjectProfileResponse,
    ProjectSearchResultItem,
    ProjectSearchResultList,
)
from metaprofile.shared.db.elasticsearch import ESRepo
from metaprofile.shared.llm.embedding import get_default_embedding_client
from metaprofile.shared.schemas.entity_project import (
    ProjectBudget,
    ProjectHistory,
    ProjectOutput,
    ProjectStatus,
    BudgetActivity,
)

logger = structlog.get_logger(__name__)

_ES_INDEX = "project_profile"

EAGER_OPTIONS = [
    selectinload(ProjectProfileORM.histories),
    selectinload(ProjectProfileORM.budgets),
    selectinload(ProjectProfileORM.outputs),
]


def orm_to_response(orm: ProjectProfileORM) -> ProjectProfileResponse:
    return ProjectProfileResponse(
        project_id=orm.project_id,
        name_cn=orm.name_cn,
        name_en=orm.name_en,
        name_other=orm.name_other,
        tech_domain=orm.tech_domain,
        sub_tech_domain=orm.sub_tech_domain,
        start_date=orm.start_date,
        cancel_date=orm.cancel_date,
        finish_date=orm.finish_date,
        status=[ProjectStatus(s) for s in orm.status],
        budget_activities=[BudgetActivity(a) for a in orm.budget_activities],
        project_no=orm.project_no,
        main_orgs=orm.main_orgs,
        undertaking_orgs=orm.undertaking_orgs,
        undertaking_enterprises=orm.undertaking_enterprises,
        managers=orm.managers,
        researchers=orm.researchers,
        background=orm.background,
        research_goal=orm.research_goal,
        research_content=orm.research_content,
        keywords=orm.keywords,
        progress=orm.progress,
        application_prospect=orm.application_prospect,
        key_dates=orm.key_dates,
        total_budget_million_usd=float(orm.total_budget_million_usd)
        if orm.total_budget_million_usd is not None
        else None,
        invested_million_usd=float(orm.invested_million_usd)
        if orm.invested_million_usd is not None
        else None,
        parent_package_name=orm.parent_package_name,
        previous_phase_name=orm.previous_phase_name,
        confidence=orm.confidence,
        veracity_score=orm.veracity_score,
        timeliness_score=orm.timeliness_score,
        data_as_of=orm.data_as_of,
        histories=[
            ProjectHistory(
                change_date=h.change_date,
                change_description=h.change_description,
            )
            for h in orm.histories
        ],
        budgets=[
            ProjectBudget(
                budget_date=b.budget_date,
                amount=float(b.amount),
            )
            for b in orm.budgets
        ],
        outputs=[
            ProjectOutput(
                name_history=o.name_history,
                formed_at=o.formed_at,
                tech_domains=o.tech_domains,
                owner_orgs=o.owner_orgs,
                related_projects=o.related_projects,
                attachments=o.attachments,
            )
            for o in orm.outputs
        ],
    )


class ProjectQueryService:
    """项目画像查询服务。"""

    def __init__(self) -> None:
        self._es = ESRepo()

    async def get_by_id(
        self, session: AsyncSession, project_id: str
    ) -> ProjectProfileResponse | None:
        stmt = (
            select(ProjectProfileORM)
            .where(ProjectProfileORM.project_id == project_id)
            .options(*EAGER_OPTIONS)
        )
        orm = (await session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return orm_to_response(orm)

    async def search(
        self, session: AsyncSession, payload: SearchRequest
    ) -> ProjectSearchResultList:
        conditions = []
        if payload.keyword:
            kw = f"%{payload.keyword}%"
            conditions.append(
                or_(
                    cast(ProjectProfileORM.name_cn, Text).ilike(kw),
                    cast(ProjectProfileORM.name_en, Text).ilike(kw),
                    ProjectProfileORM.research_goal.ilike(kw),
                )
            )
        if payload.project_domain:
            conditions.append(
                or_(
                    *[
                        cast(ProjectProfileORM.tech_domain, JSONB).contains([d])
                        for d in payload.project_domain
                    ]
                )
            )
        if payload.invention_date_from:
            conditions.append(ProjectProfileORM.start_date >= payload.invention_date_from)
        if payload.invention_date_to:
            conditions.append(ProjectProfileORM.start_date <= payload.invention_date_to)

        base_q = select(ProjectProfileORM)
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
            ProjectSearchResultItem(
                project_id=r.project_id,
                project_name_cn=r.name_cn[0] if r.name_cn else "",
                project_domain=r.tech_domain,
            )
            for r in rows
        ]
        return ProjectSearchResultList(items=items, total=total)

    async def semantic_search(
        self, payload: SemanticSearchRequest
    ) -> ProjectSearchResultList:
        vector = await get_default_embedding_client().embed_one(payload.query)

        filter_query = None
        if payload.project_domain_filter:
            filter_query = {
                "bool": {
                    "should": [
                        {"term": {"tech_domain": d}}
                        for d in payload.project_domain_filter
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
            ProjectSearchResultItem(
                project_id=h.get("entity_id", h.get("_id", "")),
                project_name_cn=h.get("name_cn", [""])[0]
                if isinstance(h.get("name_cn"), list)
                else h.get("name_cn", ""),
                project_domain=h.get("tech_domain", []),
                relevance_score=h.get("_score"),
            )
            for h in hits
        ]
        return ProjectSearchResultList(items=items, total=len(items))

    async def batch_get(
        self, session: AsyncSession, project_ids: list[str]
    ) -> list[ProjectProfileResponse]:
        stmt = (
            select(ProjectProfileORM)
            .where(ProjectProfileORM.project_id.in_(project_ids))
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
            EntityChangeLogORM.entity_type == "project",
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
                project_id=r.entity_id,
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
