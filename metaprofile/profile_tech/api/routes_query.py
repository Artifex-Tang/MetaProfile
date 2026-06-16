"""技术画像查询路由：单查询/搜索/语义搜索/批量/变更。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_tech.api.deps import get_query_service
from metaprofile.profile_tech.schemas.request import (
    BatchQueryRequest,
    SearchRequest,
    SemanticSearchRequest,
)
from metaprofile.profile_tech.schemas.response import (
    ChangeRecordList,
    TechProfileResponse,
    TechSearchResultList,
)
from metaprofile.profile_tech.services.tech_query_service import TechQueryService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()



@router.get("/profile/tech/changes", response_model=ChangeRecordList)
async def list_changes(
    since: datetime = Query(..., description="变更起始时间"),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    service: TechQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> ChangeRecordList:
    """查询指定时段内的画像字段级变更记录。"""
    return await service.list_changes(session, since=since, until=until, limit=limit)

@router.get("/profile/tech/{tech_id}", response_model=TechProfileResponse)
async def get_tech_profile(
    tech_id: str,
    service: TechQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> TechProfileResponse:
    """按 ID 查询单个技术画像详情。"""
    profile = await service.get_by_id(session, tech_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"tech_id={tech_id} not found")
    return profile


@router.post("/profile/tech/search", response_model=TechSearchResultList)
async def search_tech_profiles(
    payload: SearchRequest,
    service: TechQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> TechSearchResultList:
    """多条件组合搜索（领域 / 时间窗口 / 关键词）。"""
    return await service.search(session, payload)


@router.post("/profile/tech/semantic-search", response_model=TechSearchResultList)
async def semantic_search_tech_profiles(
    payload: SemanticSearchRequest,
    service: TechQueryService = Depends(get_query_service),
) -> TechSearchResultList:
    """基于 Embedding 的语义搜索。"""
    return await service.semantic_search(payload)


@router.post("/profile/tech/batch", response_model=list[TechProfileResponse])
async def batch_query_tech_profiles(
    payload: BatchQueryRequest,
    service: TechQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> list[TechProfileResponse]:
    """按 ID 列表批量查询。"""
    return await service.batch_get(session, payload.tech_ids)

