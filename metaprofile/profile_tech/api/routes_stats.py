"""技术画像统计路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_tech.api.deps import get_stats_service
from metaprofile.profile_tech.schemas.response import TechStatsResponse
from metaprofile.profile_tech.services.tech_stats_service import TechStatsService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/stats/tech", response_model=TechStatsResponse)
async def get_stats(
    service: TechStatsService = Depends(get_stats_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> TechStatsResponse:
    """查询技术画像综合统计：总量 / 增量 / 领域分布 / 完整度分布 / LLM 贡献度。"""
    return await service.compute(session)
