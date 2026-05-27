"""人员画像统计路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_person.api.deps import get_stats_service
from metaprofile.profile_person.schemas.response import PersonStatsResponse
from metaprofile.profile_person.services.person_stats_service import PersonStatsService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/stats/person", response_model=PersonStatsResponse)
async def get_stats(
    service: PersonStatsService = Depends(get_stats_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> PersonStatsResponse:
    """查询人员画像综合统计：总量 / 增量 / 领域分布 / 完整度分布 / LLM 贡献度。"""
    return await service.compute(session)
