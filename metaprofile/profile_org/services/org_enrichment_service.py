"""机构画像 RAG 补全服务。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_org.schemas.response import EnrichmentTaskResponse

logger = structlog.get_logger(__name__)

_ENRICH_THRESHOLD = 0.6


class OrgEnrichmentService:
    """对完整度低于阈值（默认 60%）的机构画像，触发 RAG 补全任务。"""

    async def trigger(
        self, session: AsyncSession, *, org_id: str
    ) -> EnrichmentTaskResponse | None:
        row = (
            await session.execute(
                select(OrgProfileORM.completeness).where(
                    OrgProfileORM.org_id == org_id
                )
            )
        ).first()
        if row is None:
            return None

        completeness = float(row[0])
        task_id = uuid4().hex

        if completeness < _ENRICH_THRESHOLD:
            # TODO: 推送任务到 RabbitMQ
            logger.info(
                "org_enrichment_task_queued",
                org_id=org_id,
                task_id=task_id,
                completeness=completeness,
            )
            status = "queued"
        else:
            status = "skipped"

        return EnrichmentTaskResponse(
            task_id=task_id,
            org_id=org_id,
            submitted_at=datetime.now(timezone.utc),
            current_completeness=completeness,
            status=status,
        )
