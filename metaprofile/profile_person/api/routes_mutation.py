"""人员画像变更路由：更新 / 批量导入。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_person.api.deps import get_profile_service
from metaprofile.profile_person.schemas.request import (
    BulkImportRequest,
    UpdatePersonProfileRequest,
)
from metaprofile.profile_person.schemas.response import (
    BulkImportResult,
    PersonProfileResponse,
)
from metaprofile.profile_person.services.person_profile_service import PersonProfileService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.put("/profile/person/{person_id}", response_model=PersonProfileResponse)
async def update_person_profile(
    person_id: str,
    payload: UpdatePersonProfileRequest,
    service: PersonProfileService = Depends(get_profile_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> PersonProfileResponse:
    """字段级更新画像（仅更新有值字段，保留变更日志）。"""
    updated = await service.update(session, person_id=person_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"person_id={person_id} not found")
    return updated


@router.post("/profile/person/import", response_model=BulkImportResult)
async def bulk_import(
    payload: BulkImportRequest,
    service: PersonProfileService = Depends(get_profile_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> BulkImportResult:
    """批量导入画像（异步任务，返回任务 ID）。"""
    return await service.bulk_import(session, payload=payload)
