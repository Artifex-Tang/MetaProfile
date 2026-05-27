"""机构画像变更路由：更新 / 批量导入。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_org.api.deps import get_profile_service
from metaprofile.profile_org.schemas.request import (
    BulkImportRequest,
    UpdateOrgProfileRequest,
)
from metaprofile.profile_org.schemas.response import (
    BulkImportResult,
    OrgProfileResponse,
)
from metaprofile.profile_org.services.org_profile_service import OrgProfileService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.put("/profile/org/{org_id}", response_model=OrgProfileResponse)
async def update_org_profile(
    org_id: str,
    payload: UpdateOrgProfileRequest,
    service: OrgProfileService = Depends(get_profile_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> OrgProfileResponse:
    """字段级更新画像（仅更新有值字段，保留变更日志）。"""
    updated = await service.update(session, org_id=org_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"org_id={org_id} not found")
    return updated


@router.post("/profile/org/import", response_model=BulkImportResult)
async def bulk_import(
    payload: BulkImportRequest,
    service: OrgProfileService = Depends(get_profile_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> BulkImportResult:
    """批量导入画像（异步任务，返回任务 ID）。"""
    return await service.bulk_import(session, payload=payload)
