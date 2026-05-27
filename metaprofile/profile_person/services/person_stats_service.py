"""人员画像统计服务。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_person.domain.orm_models import EntityChangeLogORM, PersonProfileORM
from metaprofile.profile_person.schemas.response import PersonStatsResponse
from metaprofile.shared.db.redis import CacheClient

logger = structlog.get_logger(__name__)

_CACHE_KEY_TYPE = "stats"
_CACHE_KEY_ID = "person:latest"
_CACHE_TTL = 3600
_PERIOD_DAYS = 30


class PersonStatsService:
    """计算人员画像综合统计：总量、本期增量、领域分布、完整度分布、LLM 贡献度。

    每日由 Celery 任务（stats_worker）预计算并缓存到 Redis，
    API 调用直接读缓存，缓存失效时回退到实时计算。
    """

    def __init__(self) -> None:
        self._cache = CacheClient()

    async def compute(self, session: AsyncSession) -> PersonStatsResponse:
        cached = await self._cache.get(_CACHE_KEY_TYPE, _CACHE_KEY_ID)
        if cached:
            return PersonStatsResponse(**cached)

        result = await self._compute_live(session)
        await self._cache.set(
            _CACHE_KEY_TYPE,
            _CACHE_KEY_ID,
            result.model_dump(mode="json"),
            ttl=_CACHE_TTL,
        )
        return result

    async def _compute_live(self, session: AsyncSession) -> PersonStatsResponse:
        total: int = (
            await session.execute(
                select(func.count()).select_from(PersonProfileORM)
            )
        ).scalar_one()

        period_start = datetime.now(timezone.utc) - timedelta(days=_PERIOD_DAYS)

        new_count: int = (
            await session.execute(
                select(func.count())
                .select_from(EntityChangeLogORM)
                .where(
                    EntityChangeLogORM.entity_type == "person",
                    EntityChangeLogORM.field == "*",
                    EntityChangeLogORM.changed_at >= period_start,
                )
            )
        ).scalar_one()

        updated_count: int = (
            await session.execute(
                select(func.count(EntityChangeLogORM.entity_id.distinct()))
                .where(
                    EntityChangeLogORM.entity_type == "person",
                    EntityChangeLogORM.field != "*",
                    EntityChangeLogORM.changed_at >= period_start,
                )
            )
        ).scalar_one()

        total_changes: int = (
            await session.execute(
                select(func.count())
                .select_from(EntityChangeLogORM)
                .where(EntityChangeLogORM.entity_type == "person")
            )
        ).scalar_one()

        llm_count: int = (
            await session.execute(
                select(func.count())
                .select_from(EntityChangeLogORM)
                .where(
                    EntityChangeLogORM.entity_type == "person",
                    EntityChangeLogORM.method == "llm_extract",
                )
            )
        ).scalar_one()

        llm_ratio = llm_count / total_changes if total_changes > 0 else 0.0

        domain_rows = (
            await session.execute(
                text(
                    "SELECT domain_val, COUNT(*) AS cnt "
                    "FROM person_profile, "
                    "jsonb_array_elements_text(professional_domains::jsonb) AS domain_val "
                    "GROUP BY domain_val ORDER BY cnt DESC LIMIT 20"
                )
            )
        ).all()
        domain_dist = {str(row[0]): int(row[1]) for row in domain_rows}

        hist_rows = (
            await session.execute(
                text(
                    "SELECT CASE "
                    "  WHEN completeness < 0.3 THEN '0-30' "
                    "  WHEN completeness < 0.6 THEN '30-60' "
                    "  WHEN completeness < 0.8 THEN '60-80' "
                    "  ELSE '80-100' END AS bucket, "
                    "COUNT(*) AS cnt FROM person_profile GROUP BY bucket"
                )
            )
        ).all()
        completeness_hist = {str(row[0]): int(row[1]) for row in hist_rows}

        return PersonStatsResponse(
            total=total,
            new_this_period=new_count,
            updated_this_period=updated_count,
            domain_distribution=domain_dist,
            completeness_histogram=completeness_hist,
            llm_contribution_ratio=round(llm_ratio, 4),
            updated_at=datetime.now(timezone.utc),
        )
