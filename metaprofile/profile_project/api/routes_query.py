"""项目画像查询路由：单查询/搜索/语义搜索/批量/变更。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_project.api.deps import get_query_service
from metaprofile.profile_project.schemas.request import (
    BatchQueryRequest,
    SearchRequest,
    SemanticSearchRequest,
)
from metaprofile.profile_project.schemas.response import (
    ChangeRecordList,
    ProjectProfileResponse,
    ProjectSearchResultList,
)
from metaprofile.profile_project.services.project_query_service import ProjectQueryService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/profile/project/{project_id}", response_model=ProjectProfileResponse)
async def get_project_profile(
    project_id: str,
    service: ProjectQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> ProjectProfileResponse:
    """按 ID 查询单个项目画像详情。"""
    profile = await service.get_by_id(session, project_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"project_id={project_id} not found")
    return profile


@router.post("/profile/project/search", response_model=ProjectSearchResultList)
async def search_project_profiles(
    payload: SearchRequest,
    service: ProjectQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> ProjectSearchResultList:
    """多条件组合搜索（领域 / 时间窗口 / 关键词）。"""
    return await service.search(session, payload)


@router.post("/profile/project/semantic-search", response_model=ProjectSearchResultList)
async def semantic_search_project_profiles(
    payload: SemanticSearchRequest,
    service: ProjectQueryService = Depends(get_query_service),
) -> ProjectSearchResultList:
    """基于 Embedding 的语义搜索。"""
    return await service.semantic_search(payload)


@router.post("/profile/project/batch", response_model=list[ProjectProfileResponse])
async def batch_query_project_profiles(
    payload: BatchQueryRequest,
    service: ProjectQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> list[ProjectProfileResponse]:
    """按 ID 列表批量查询。"""
    return await service.batch_get(session, payload.project_ids)


@router.get("/profile/project/changes", response_model=ChangeRecordList)
async def list_changes(
    since: datetime = Query(..., description="变更起始时间"),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    service: ProjectQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> ChangeRecordList:
    """查询指定时段内的画像字段级变更记录。"""
    return await service.list_changes(session, since=since, until=until, limit=limit)
