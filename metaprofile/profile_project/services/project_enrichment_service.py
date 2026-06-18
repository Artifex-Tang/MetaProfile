"""项目画像 RAG 补全服务。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from celery.result import AsyncResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.profile_project.schemas.response import EnrichmentTaskResponse
from metaprofile.shared.worker.celery_app import celery_app
from metaprofile.shared.worker.enrich_tasks import enrich_project

logger = structlog.get_logger(__name__)

_ENRICH_THRESHOLD = 0.6


class ProjectEnrichmentService:
    """对完整度低于阈值（默认 60%）的项目画像，派发异步 celery 补全任务。

    Worker 消费 enrich_project → shared/enrich/orm_enricher 直写 typed ORM
    （LLM 填缺失字段 + 重算 completeness + data_as_of + ChangeLog）。
    """

    async def trigger(
        self, session: AsyncSession, *, project_id: str
    ) -> EnrichmentTaskResponse | None:
        row = (
            await session.execute(
                select(ProjectProfileORM.completeness).where(
                    ProjectProfileORM.project_id == project_id
                )
            )
        ).first()
        if row is None:
            return None

        completeness = float(row[0])
        now = datetime.now(timezone.utc)

        if completeness < _ENRICH_THRESHOLD:
            result = enrich_project.delay(project_id)
            logger.info(
                "enrichment_task_dispatched",
                project_id=project_id,
                task_id=result.id,
                completeness=completeness,
            )
            return EnrichmentTaskResponse(
                task_id=result.id,
                project_id=project_id,
                submitted_at=now,
                current_completeness=completeness,
                status="queued",
            )

        logger.info(
            "enrichment_skipped_completeness_sufficient",
            project_id=project_id,
            completeness=completeness,
        )
        return EnrichmentTaskResponse(
            task_id=uuid4().hex,
            project_id=project_id,
            submitted_at=now,
            current_completeness=completeness,
            status="skipped",
        )

    async def get_task_status(self, task_id: str) -> dict:
        """查询 celery 任务状态（前端轮询）。"""
        res = AsyncResult(task_id, app=celery_app)
        payload: dict = {"task_id": task_id, "state": res.state}
        if res.state == "SUCCESS":
            result = res.result or {}
            payload["status"] = result.get("status")
            payload["completeness_after"] = result.get("completeness_after")
            payload["filled_fields"] = result.get("filled_fields", [])
            payload["error"] = result.get("error")
        elif res.state == "FAILURE":
            payload["status"] = "failed"
            payload["error"] = str(res.result)
        else:
            payload["status"] = "pending"
        return payload
