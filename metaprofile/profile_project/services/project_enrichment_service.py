"""项目画像 RAG 补全服务。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.profile_project.schemas.response import EnrichmentTaskResponse

logger = structlog.get_logger(__name__)

_ENRICH_THRESHOLD = 0.6


class ProjectEnrichmentService:
    """对完整度低于阈值（默认 60%）的项目画像，触发 RAG 补全任务。

    流程：
    1. 校验 project_id 存在
    2. 计算当前完整度
    3. 若 < 阈值，向 RabbitMQ 投递补全任务，返回 task_id
    4. Worker 消费任务：foundation/enrichment 模块执行 RAG 检索 + LLM 抽取，
       confidence ≥ 0.8 自动入库，0.6~0.8 进入审核队列，<0.6 丢弃
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
        task_id = uuid4().hex

        if completeness < _ENRICH_THRESHOLD:
            # TODO: 推送任务到 RabbitMQ
            logger.info(
                "enrichment_task_queued",
                project_id=project_id,
                task_id=task_id,
                completeness=completeness,
            )
            status = "queued"
        else:
            logger.info(
                "enrichment_skipped_completeness_sufficient",
                project_id=project_id,
                completeness=completeness,
            )
            status = "skipped"

        return EnrichmentTaskResponse(
            task_id=task_id,
            project_id=project_id,
            submitted_at=datetime.now(timezone.utc),
            current_completeness=completeness,
            status=status,
        )
