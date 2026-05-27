"""技术画像变更路由：更新 / 批量导入。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_tech.api.deps import get_profile_service
from metaprofile.profile_tech.schemas.request import (
    BulkImportRequest,
    UpdateTechProfileRequest,
)
from metaprofile.profile_tech.schemas.response import (
    BulkImportResult,
    TechProfileResponse,
)
from metaprofile.profile_tech.services.tech_profile_service import TechProfileService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.put("/profile/tech/{tech_id}", response_model=TechProfileResponse)
async def update_tech_profile(
    tech_id: str,
    payload: UpdateTechProfileRequest,
    service: TechProfileService = Depends(get_profile_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> TechProfileResponse:
    """字段级更新画像（仅更新有值字段，保留变更日志）。"""
    updated = await service.update(session, tech_id=tech_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"tech_id={tech_id} not found")
    return updated


@router.post("/profile/tech/import", response_model=BulkImportResult)
async def bulk_import(
    payload: BulkImportRequest,
    service: TechProfileService = Depends(get_profile_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> BulkImportResult:
    """批量导入画像（异步任务，返回任务 ID）。"""
    return await service.bulk_import(session, payload=payload)
