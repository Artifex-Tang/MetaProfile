"""机构画像统计服务。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_org.domain.orm_models import EntityChangeLogORM, OrgProfileORM
from metaprofile.profile_org.schemas.response import OrgStatsResponse
from metaprofile.shared.db.redis import CacheClient

logger = structlog.get_logger(__name__)

_CACHE_KEY_TYPE = "stats"
_CACHE_KEY_ID = "org:latest"
_CACHE_TTL = 3600
_PERIOD_DAYS = 30


class OrgStatsService:
    """计算机构画像综合统计：总量、本期增量、领域分布、完整度分布、LLM 贡献度。"""

    def __init__(self) -> None:
        self._cache = CacheClient()

    async def compute(self, session: AsyncSession) -> OrgStatsResponse:
        cached = await self._cache.get(_CACHE_KEY_TYPE, _CACHE_KEY_ID)
        if cached:
            return OrgStatsResponse(**cached)

        result = await self._compute_live(session)
        await self._cache.set(
            _CACHE_KEY_TYPE,
            _CACHE_KEY_ID,
            result.model_dump(mode="json"),
            ttl=_CACHE_TTL,
        )
        return result

    async def _compute_live(self, session: AsyncSession) -> OrgStatsResponse:
        total: int = (
            await session.execute(
                select(func.count()).select_from(OrgProfileORM)
            )
        ).scalar_one()

        period_start = datetime.now(timezone.utc) - timedelta(days=_PERIOD_DAYS)

        new_count: int = (
            await session.execute(
                select(func.count())
                .select_from(EntityChangeLogORM)
                .where(
                    EntityChangeLogORM.entity_type == "org",
                    EntityChangeLogORM.field == "*",
                    EntityChangeLogORM.changed_at >= period_start,
                )
            )
        ).scalar_one()

        updated_count: int = (
            await session.execute(
                select(func.count(EntityChangeLogORM.entity_id.distinct()))
                .where(
                    EntityChangeLogORM.entity_type == "org",
                    EntityChangeLogORM.field != "*",
                    EntityChangeLogORM.changed_at >= period_start,
                )
            )
        ).scalar_one()

        total_changes: int = (
            await session.execute(
                select(func.count())
                .select_from(EntityChangeLogORM)
                .where(EntityChangeLogORM.entity_type == "org")
            )
        ).scalar_one()

        llm_count: int = (
            await session.execute(
                select(func.count())
                .select_from(EntityChangeLogORM)
                .where(
                    EntityChangeLogORM.entity_type == "org",
                    EntityChangeLogORM.method == "llm_extract",
                )
            )
        ).scalar_one()

        llm_ratio = llm_count / total_changes if total_changes > 0 else 0.0

        domain_rows = (
            await session.execute(
                text(
                    "SELECT domain_val, COUNT(*) AS cnt "
                    "FROM org_profile, "
                    "jsonb_array_elements_text(tech_domains::jsonb) AS domain_val "
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
                    "COUNT(*) AS cnt FROM org_profile GROUP BY bucket"
                )
            )
        ).all()
        completeness_hist = {str(row[0]): int(row[1]) for row in hist_rows}

        return OrgStatsResponse(
            total=total,
            new_this_period=new_count,
            updated_this_period=updated_count,
            domain_distribution=domain_dist,
            completeness_histogram=completeness_hist,
            llm_contribution_ratio=round(llm_ratio, 4),
            updated_at=datetime.now(timezone.utc),
        )
