"""技术画像关系查询路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_tech.api.deps import get_relation_service
from metaprofile.profile_tech.schemas.request import RelationPathRequest
from metaprofile.profile_tech.schemas.response import (
    RelationList,
    RelationPathResult,
    TechRelationResult,
)
from metaprofile.profile_tech.services.tech_relation_service import (
    TechRelationService,
)
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.get("/relation/tech/{tech_id}", response_model=RelationList)
async def list_relations(
    tech_id: str,
    relation_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    service: TechRelationService = Depends(get_relation_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> RelationList:
    """查询指定技术的全部关系列表。"""
    return await service.list_relations(
        session, tech_id=tech_id, relation_type=relation_type, limit=limit
    )


@router.post("/relation/tech/path", response_model=RelationPathResult)
async def find_relation_path(
    payload: RelationPathRequest,
    service: TechRelationService = Depends(get_relation_service),
) -> RelationPathResult:
    """查询两个实体间的关系路径（基于 Neo4j 最短路径）。"""
    return await service.find_path(
        from_id=payload.from_id, to_id=payload.to_id, max_depth=payload.max_depth
    )


@router.get(
    "/relation/tech/{tech_id}/tech-relation", response_model=TechRelationResult
)
async def get_tech_relation(
    tech_id: str,
    viewpoint: str = Query(default="evolve", pattern="^(evolve|prereq)$"),
    depth: int = Query(default=4, ge=1, le=4),
    service: TechRelationService = Depends(get_relation_service),
) -> TechRelationResult:
    """查询技术关系图（演进链 / 前置树，双向遍历 TECH_EVOLVE/TECH_PREREQ）。"""
    return await service.find_tech_relation(
        tech_id=tech_id, viewpoint=viewpoint, depth=depth,
    )
