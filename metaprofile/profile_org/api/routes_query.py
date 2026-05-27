"""机构画像查询路由：单查询/搜索/语义搜索/批量/变更。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_org.api.deps import get_query_service
from metaprofile.profile_org.schemas.request import (
    BatchQueryRequest,
    SearchRequest,
    SemanticSearchRequest,
)
from metaprofile.profile_org.schemas.response import (
    ChangeRecordList,
    OrgProfileResponse,
    OrgSearchResultList,
)
from metaprofile.profile_org.services.org_query_service import OrgQueryService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/profile/org/{org_id}", response_model=OrgProfileResponse)
async def get_org_profile(
    org_id: str,
    service: OrgQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> OrgProfileResponse:
    """按 ID 查询单个机构画像详情。"""
    profile = await service.get_by_id(session, org_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"org_id={org_id} not found")
    return profile


@router.post("/profile/org/search", response_model=OrgSearchResultList)
async def search_org_profiles(
    payload: SearchRequest,
    service: OrgQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> OrgSearchResultList:
    """多条件组合搜索（领域 / 时间窗口 / 关键词）。"""
    return await service.search(session, payload)


@router.post("/profile/org/semantic-search", response_model=OrgSearchResultList)
async def semantic_search_org_profiles(
    payload: SemanticSearchRequest,
    service: OrgQueryService = Depends(get_query_service),
) -> OrgSearchResultList:
    """基于 Embedding 的语义搜索。"""
    return await service.semantic_search(payload)


@router.post("/profile/org/batch", response_model=list[OrgProfileResponse])
async def batch_query_org_profiles(
    payload: BatchQueryRequest,
    service: OrgQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> list[OrgProfileResponse]:
    """按 ID 列表批量查询。"""
    return await service.batch_get(session, payload.org_ids)


@router.get("/profile/org/changes", response_model=ChangeRecordList)
async def list_changes(
    since: datetime = Query(..., description="变更起始时间"),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    service: OrgQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> ChangeRecordList:
    """查询指定时段内的画像字段级变更记录。"""
    return await service.list_changes(session, since=since, until=until, limit=limit)
