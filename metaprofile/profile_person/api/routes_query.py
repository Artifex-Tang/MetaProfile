"""人员画像查询路由：单查询/搜索/语义搜索/批量/变更。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_person.api.deps import get_query_service
from metaprofile.profile_person.schemas.request import (
    BatchQueryRequest,
    SearchRequest,
    SemanticSearchRequest,
)
from metaprofile.profile_person.schemas.response import (
    ChangeRecordList,
    PersonProfileResponse,
    PersonSearchResultList,
)
from metaprofile.profile_person.services.person_query_service import PersonQueryService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/profile/person/{person_id}", response_model=PersonProfileResponse)
async def get_person_profile(
    person_id: str,
    service: PersonQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> PersonProfileResponse:
    """按 ID 查询单个人员画像详情。"""
    profile = await service.get_by_id(session, person_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"person_id={person_id} not found")
    return profile


@router.post("/profile/person/search", response_model=PersonSearchResultList)
async def search_person_profiles(
    payload: SearchRequest,
    service: PersonQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> PersonSearchResultList:
    """多条件组合搜索（领域 / 时间窗口 / 关键词）。"""
    return await service.search(session, payload)


@router.post("/profile/person/semantic-search", response_model=PersonSearchResultList)
async def semantic_search_person_profiles(
    payload: SemanticSearchRequest,
    service: PersonQueryService = Depends(get_query_service),
) -> PersonSearchResultList:
    """基于 Embedding 的语义搜索。"""
    return await service.semantic_search(payload)


@router.post("/profile/person/batch", response_model=list[PersonProfileResponse])
async def batch_query_person_profiles(
    payload: BatchQueryRequest,
    service: PersonQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> list[PersonProfileResponse]:
    """按 ID 列表批量查询。"""
    return await service.batch_get(session, payload.person_ids)


@router.get("/profile/person/changes", response_model=ChangeRecordList)
async def list_changes(
    since: datetime = Query(..., description="变更起始时间"),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    service: PersonQueryService = Depends(get_query_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> ChangeRecordList:
    """查询指定时段内的画像字段级变更记录。"""
    return await service.list_changes(session, since=since, until=until, limit=limit)
