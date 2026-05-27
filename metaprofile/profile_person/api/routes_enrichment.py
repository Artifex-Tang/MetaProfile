"""人员画像 RAG 补全路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_person.api.deps import get_enrichment_service
from metaprofile.profile_person.schemas.response import EnrichmentTaskResponse
from metaprofile.profile_person.services.person_enrichment_service import (
    PersonEnrichmentService,
)
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.post("/profile/person/{person_id}/enrich", response_model=EnrichmentTaskResponse)
async def trigger_enrichment(
    person_id: str,
    service: PersonEnrichmentService = Depends(get_enrichment_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> EnrichmentTaskResponse:
    """对完整度低于阈值的人员画像，触发 RAG 驱动的字段补全任务。"""
    task = await service.trigger(session, person_id=person_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"person_id={person_id} not found")
    return task
