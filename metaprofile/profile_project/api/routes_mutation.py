"""项目画像变更路由：更新 / 批量导入。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_project.api.deps import get_profile_service
from metaprofile.profile_project.schemas.request import (
    BulkImportRequest,
    UpdateProjectProfileRequest,
)
from metaprofile.profile_project.schemas.response import (
    BulkImportResult,
    ProjectProfileResponse,
)
from metaprofile.profile_project.services.project_profile_service import ProjectProfileService
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.put("/profile/project/{project_id}", response_model=ProjectProfileResponse)
async def update_project_profile(
    project_id: str,
    payload: UpdateProjectProfileRequest,
    service: ProjectProfileService = Depends(get_profile_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> ProjectProfileResponse:
    """字段级更新画像（仅更新有值字段，保留变更日志）。"""
    updated = await service.update(session, project_id=project_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"project_id={project_id} not found")
    return updated


@router.post("/profile/project/import", response_model=BulkImportResult)
async def bulk_import(
    payload: BulkImportRequest,
    service: ProjectProfileService = Depends(get_profile_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> BulkImportResult:
    """批量导入画像（异步任务，返回任务 ID）。"""
    return await service.bulk_import(session, payload=payload)
