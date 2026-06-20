"""scan celery 任务：前沿技术 LLM 验证（点「验证」异步跑 FrontierAgentValidator）。

替代原先纯人工 status 翻转 —— 现在点验证 → 异步 LLM agent 4 步验证 →
按判定(是/否/待定)回写 FrontierTechORM.status + llm_verdict/evidence。
"""
from __future__ import annotations

import structlog
from typing import Any

from metaprofile.scan_monitor.domain.orm_models import FrontierTechORM
from metaprofile.scan_monitor.services.llm_agent_validator import FrontierAgentValidator
from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.worker.async_runner import run_async
from metaprofile.shared.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _async_verify(frontier_id: int, task_id: str) -> dict[str, Any]:
    try:
        async with get_session() as session:
            row = await session.get(FrontierTechORM, frontier_id)
            if row is None:
                return {"status": "error", "error": "frontier tech not found"}
            evidence_pack = (
                f"五维信号：突现={row.burst_score:.2f} 专利={row.patent_score:.2f} "
                f"引用={row.citation_score:.2f} 投资={row.invest_score:.2f} "
                f"政策={row.policy_score:.2f}"
            )
            verdict = await FrontierAgentValidator(LLMGateway()).validate(
                tech_name=row.tech_name, evidence_pack=evidence_pack
            )
            row.llm_validated = verdict.final_decision == "是"
            row.llm_verdict = verdict.final_decision
            row.llm_evidence = verdict.evidence
            if verdict.final_decision == "是":
                row.status = "validated"
            elif verdict.final_decision == "否":
                row.status = "rejected"
            # "待定" → 保持原 status（通常 pending）
            logger.info(
                "frontier_verified",
                frontier_id=frontier_id, task_id=task_id,
                verdict=verdict.final_decision, status=row.status,
            )
            return {
                "status": "done",
                "llm_verdict": verdict.final_decision,
                "frontier_status": row.status,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("frontier_verify_failed", frontier_id=frontier_id, error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.scan.verify_frontier_tech", bind=True)
def verify_frontier_tech(self, frontier_id: int) -> dict[str, Any]:
    # run_async 复用 worker 持久 loop(非 asyncio.run 每次建+关)→ 避免 asyncpg
    # 连接绑死已关 loop 的 'Event loop is closed' 跨任务错误。
    return run_async(_async_verify(frontier_id, self.request.id))
