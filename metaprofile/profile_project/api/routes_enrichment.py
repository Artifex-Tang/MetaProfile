"""项目画像 RAG 补全路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_project.api.deps import get_enrichment_service
from metaprofile.profile_project.schemas.response import EnrichmentTaskResponse
from metaprofile.profile_project.services.project_enrichment_service import (
    ProjectEnrichmentService,
)
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.post("/profile/project/{project_id}/enrich", response_model=EnrichmentTaskResponse)
async def trigger_enrichment(
    project_id: str,
    service: ProjectEnrichmentService = Depends(get_enrichment_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> EnrichmentTaskResponse:
    """对完整度低于阈值的项目画像，触发 RAG 驱动的字段补全任务。"""
    task = await service.trigger(session, project_id=project_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"project_id={project_id} not found")
    return task


@router.get("/profile/project/enrich/task/{task_id}")
async def get_enrichment_task_status(
    task_id: str,
    service: ProjectEnrichmentService = Depends(get_enrichment_service),
) -> dict:
    """查询补全任务状态（celery AsyncResult，前端轮询）。"""
    return await service.get_task_status(task_id)
