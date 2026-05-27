"""人员画像关系查询路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_person.api.deps import get_relation_service
from metaprofile.profile_person.schemas.request import RelationPathRequest
from metaprofile.profile_person.schemas.response import (
    RelationList,
    RelationPathResult,
)
from metaprofile.profile_person.services.person_relation_service import (
    PersonRelationService,
)
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/relation/person/{person_id}", response_model=RelationList)
async def list_relations(
    person_id: str,
    relation_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    service: PersonRelationService = Depends(get_relation_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> RelationList:
    """查询指定人员的全部关系列表。"""
    return await service.list_relations(
        session, person_id=person_id, relation_type=relation_type, limit=limit
    )


@router.post("/relation/person/path", response_model=RelationPathResult)
async def find_relation_path(
    payload: RelationPathRequest,
    service: PersonRelationService = Depends(get_relation_service),
) -> RelationPathResult:
    """查询两个实体间的关系路径（基于 Neo4j 最短路径）。"""
    return await service.find_path(
        from_id=payload.from_id, to_id=payload.to_id, max_depth=payload.max_depth
    )
