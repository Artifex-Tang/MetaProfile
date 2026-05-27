"""扫描监测主服务：协调五维信号 + 融合 + LLM 验证 + TRL 标注，写入 frontier_tech 表。"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.scan_monitor.domain.orm_models import FrontierTechORM, ScanAlertORM
from metaprofile.scan_monitor.services.fusion_scorer import FrontierTechFusionScorer
from metaprofile.scan_monitor.services.llm_agent_validator import FrontierAgentValidator
from metaprofile.scan_monitor.services.signal_burst import BurstSignalScorer
from metaprofile.scan_monitor.services.signal_citation import CitationSignalScorer
from metaprofile.scan_monitor.services.signal_invest import InvestSignalScorer
from metaprofile.scan_monitor.services.signal_patent import PatentSignalScorer
from metaprofile.scan_monitor.services.signal_policy import PolicySignalScorer
from metaprofile.scan_monitor.services.trl_annotator import TRLAnnotator
from metaprofile.shared.llm.gateway import LLMGateway

logger = structlog.get_logger(__name__)

_FRONTIER_THRESHOLD = 0.55   # 融合分阈值，超过即认为是前沿技术
_ALERT_THRESHOLD = 0.80      # 融合分超过此值触发 critical 告警


class ScanMonitorService:
    """前沿技术扫描监测主服务。"""

    def __init__(self, db: AsyncSession, gateway: LLMGateway) -> None:
        self._db = db
        self._burst = BurstSignalScorer()
        self._patent = PatentSignalScorer()
        self._citation = CitationSignalScorer()
        self._invest = InvestSignalScorer()
        self._policy = PolicySignalScorer()
        self._fusion = FrontierTechFusionScorer()
        self._validator = FrontierAgentValidator(gateway)
        self._trl = TRLAnnotator(gateway)

    async def run_scan(
        self,
        *,
        candidates: list[dict],
        period_from: date,
        period_to: date,
        scan_task_id: str | None = None,
    ) -> list[FrontierTechORM]:
        """对候选技术列表逐一评估，写入数据库，返回已持久化的记录列表。

        candidates 格式：[{"tech_name": str, "domain": str|None, "tech_id": str|None, ...}]
        """
        task_id = scan_task_id or f"scan-{uuid.uuid4().hex[:12]}"
        results: list[FrontierTechORM] = []

        for cand in candidates:
            tech_name: str = cand["tech_name"]
            domain: str | None = cand.get("domain")
            tech_id: str | None = cand.get("tech_id")

            try:
                orm = await self._evaluate_candidate(
                    tech_name=tech_name,
                    domain=domain,
                    tech_id=tech_id,
                    period_from=period_from,
                    period_to=period_to,
                    task_id=task_id,
                )
                self._db.add(orm)
                results.append(orm)

                if orm.fusion_score >= _ALERT_THRESHOLD:
                    await self._fire_alert(orm)
            except Exception as exc:
                logger.error("scan_candidate_failed", tech_name=tech_name, error=str(exc))

        await self._db.flush()
        return results

    async def _evaluate_candidate(
        self,
        *,
        tech_name: str,
        domain: str | None,
        tech_id: str | None,
        period_from: date,
        period_to: date,
        task_id: str,
    ) -> FrontierTechORM:
        score_kw = dict(
            tech_name=tech_name,
            domain=domain,
            period_from=period_from,
            period_to=period_to,
        )
        burst = await self._burst.score(**score_kw)
        patent = await self._patent.score(**score_kw)
        citation = await self._citation.score(**score_kw)
        invest = await self._invest.score(**score_kw)
        policy = await self._policy.score(**score_kw)
        fusion = self._fusion.fuse(
            burst=burst, patent=patent, citation=citation,
            invest=invest, policy=policy,
        )

        llm_validated = False
        llm_verdict: str | None = None
        llm_evidence: str | None = None
        trl_level: int | None = None
        status = "pending"

        if fusion >= _FRONTIER_THRESHOLD:
            evidence_pack = (
                f"五维信号：突现={burst:.2f} 专利={patent:.2f} "
                f"引用={citation:.2f} 投资={invest:.2f} 政策={policy:.2f}"
            )
            try:
                verdict = await self._validator.validate(
                    tech_name=tech_name, evidence_pack=evidence_pack
                )
                llm_validated = verdict.final_decision == "是"
                llm_verdict = verdict.final_decision
                llm_evidence = verdict.evidence
                status = "validated" if llm_validated else "rejected"
            except Exception as exc:
                logger.warning("llm_validation_failed", tech_name=tech_name, error=str(exc))

            if llm_validated:
                try:
                    trl_ann = await self._trl.annotate(
                        tech_name=tech_name,
                        tech_summary=llm_evidence or tech_name,
                        current_status=f"融合分={fusion:.2f}",
                    )
                    trl_level = trl_ann.trl_level
                except Exception as exc:
                    logger.warning("trl_annotation_failed", tech_name=tech_name, error=str(exc))

        return FrontierTechORM(
            scan_task_id=task_id,
            tech_id=tech_id,
            tech_name=tech_name,
            tech_domain=[domain] if domain else [],
            period_from=period_from,
            period_to=period_to,
            burst_score=burst,
            patent_score=patent,
            citation_score=citation,
            invest_score=invest,
            policy_score=policy,
            fusion_score=fusion,
            llm_validated=llm_validated,
            llm_verdict=llm_verdict,
            llm_evidence=llm_evidence,
            trl_level=trl_level,
            status=status,
        )

    async def _fire_alert(self, orm: FrontierTechORM) -> None:
        alert = ScanAlertORM(
            tech_name=orm.tech_name,
            alert_type="burst",
            severity="critical",
            message=f"前沿技术融合分={orm.fusion_score:.2f}，超过告警阈值 {_ALERT_THRESHOLD}",
            fired_at=datetime.now(timezone.utc),
        )
        self._db.add(alert)
