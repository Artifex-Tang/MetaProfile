"""LLM 补全（enrich）任务列表 API —— 与采集任务并列于 Settings 任务列表。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.settings_api.domain.orm_models import EnrichmentTaskORM
from metaprofile.settings_api.schemas.models import EnrichmentTaskOut
from metaprofile.shared.db.session import get_db

router = APIRouter(prefix="/api/v1/settings", tags=["enrichment-tasks"])


@router.get("/enrichment-tasks", response_model=list[EnrichmentTaskOut])
async def list_enrichment_tasks(
    profile_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[EnrichmentTaskORM]:
    """enrich 任务历史（trigger 写 queued，worker 写终态）。按 id 倒序。"""
    q = select(EnrichmentTaskORM).order_by(desc(EnrichmentTaskORM.id)).limit(limit)
    if profile_type:
        q = q.where(EnrichmentTaskORM.profile_type == profile_type)
    if status:
        q = q.where(EnrichmentTaskORM.status == status)
    rows = (await db.execute(q)).scalars().all()
    return list(rows)
