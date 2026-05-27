"""机构画像统计路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_org.api.deps import get_stats_service
from metaprofile.profile_org.schemas.response import OrgStatsResponse
from metaprofile.profile_org.services.org_stats_service import OrgStatsService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/stats/org", response_model=OrgStatsResponse)
async def get_stats(
    service: OrgStatsService = Depends(get_stats_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> OrgStatsResponse:
    """查询机构画像综合统计：总量 / 增量 / 领域分布 / 完整度分布 / LLM 贡献度。"""
    return await service.compute(session)
