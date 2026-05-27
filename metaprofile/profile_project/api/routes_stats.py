"""项目画像统计路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_project.api.deps import get_stats_service
from metaprofile.profile_project.schemas.response import ProjectStatsResponse
from metaprofile.profile_project.services.project_stats_service import ProjectStatsService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/stats/project", response_model=ProjectStatsResponse)
async def get_stats(
    service: ProjectStatsService = Depends(get_stats_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> ProjectStatsResponse:
    """查询项目画像综合统计：总量 / 增量 / 领域分布 / 完整度分布 / LLM 贡献度。"""
    return await service.compute(session)
