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


@router.get("/profile/person/enrich/task/{task_id}")
async def get_enrichment_task_status(
    task_id: str,
    service: PersonEnrichmentService = Depends(get_enrichment_service),
) -> dict:
    """查询补全任务状态（celery AsyncResult，前端轮询）。"""
    return await service.get_task_status(task_id)


# ── 翻译（en→cn name_cn 补全，#9 非中文策略）──
from metaprofile.shared.worker.translate_tasks import translate_name  # noqa: E402
from celery.result import AsyncResult  # noqa: E402
from metaprofile.shared.worker.celery_app import celery_app as _celery_app  # noqa: E402


@router.post("/profile/person/{person_id}/translate")
async def translate_person_name(person_id: str) -> dict:
    res = translate_name.delay("person", person_id)
    return {"task_id": res.id}


@router.get("/profile/person/translate/task/{task_id}")
async def translate_person_task_status(task_id: str) -> dict:
    r = AsyncResult(task_id, app=_celery_app)
    return {"task_id": task_id, "state": r.state, "result": r.result if r.ready() else None}
