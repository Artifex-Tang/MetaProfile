"""机构画像 RAG 补全路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_org.api.deps import get_enrichment_service
from metaprofile.profile_org.schemas.response import EnrichmentTaskResponse
from metaprofile.profile_org.services.org_enrichment_service import (
    OrgEnrichmentService,
)
from metaprofile.shared.db.postgres import fastapi_session_dep

router = APIRouter()


@router.post("/profile/org/{org_id}/enrich", response_model=EnrichmentTaskResponse)
async def trigger_enrichment(
    org_id: str,
    service: OrgEnrichmentService = Depends(get_enrichment_service),
    session: AsyncSession = Depends(fastapi_session_dep),
) -> EnrichmentTaskResponse:
    """对完整度低于阈值的机构画像，触发 RAG 驱动的字段补全任务。"""
    task = await service.trigger(session, org_id=org_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"org_id={org_id} not found")
    return task


@router.get("/profile/org/enrich/task/{task_id}")
async def get_enrichment_task_status(
    task_id: str,
    service: OrgEnrichmentService = Depends(get_enrichment_service),
) -> dict:
    """查询补全任务状态（celery AsyncResult，前端轮询）。"""
    return await service.get_task_status(task_id)


# ── 翻译（en→cn name_cn 补全，#9 非中文策略）──
from metaprofile.shared.worker.translate_tasks import translate_name  # noqa: E402
from celery.result import AsyncResult  # noqa: E402
from metaprofile.shared.worker.celery_app import celery_app as _celery_app  # noqa: E402


@router.post("/profile/org/{org_id}/translate")
async def translate_org_name(org_id: str) -> dict:
    res = translate_name.delay("org", org_id)
    return {"task_id": res.id}


@router.get("/profile/org/translate/task/{task_id}")
async def translate_org_task_status(task_id: str) -> dict:
    r = AsyncResult(task_id, app=_celery_app)
    return {"task_id": task_id, "state": r.state, "result": r.result if r.ready() else None}
