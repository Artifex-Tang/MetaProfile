"""E5 LLM 演进链升级(2026-10-15):概念对 → LLM 判演进方向。

v1 时序启发(同域证据相邻, conf 0.3)盲排;本升级对高价值概念对
(共现文档 ≥ min_codocs 的对)用 LLM 判 A→B / B→A / 无关,
命中写 TECH_EVOLVE 边 conf=0.7·llm_confidence(method=LLM)。
配额纪律:只打 top_n 对,每对 1 次调用。
"""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.foundation.relation.triple_writer import TripleWriter
from metaprofile.foundation.storage.neo4j_repo import FoundationNeo4jRepo
from metaprofile.ingest_ods.domain.orm_models import TechEvidenceORM
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import EntityType, ProfileBase, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple, RelationType

logger = structlog.get_logger(__name__)


class EvolveVerdict(ProfileBase):
    direction: str = Field(..., description="A_to_B | B_to_A | unrelated")
    rationale: str = Field(..., description="判定依据(技术演化逻辑)")
    confidence: float = Field(..., ge=0.0, le=1.0)


SYSTEM_PROMPT = """你是技术演化分析专家。判断两个技术概念之间的演进关系:
- A_to_B: B 是 A 的演进/升级/后代(B 解决了 A 的局限,或建立在 A 之上)
- B_to_A: 反向
- unrelated: 无明确演化关系(并列/无关)
判据:技术代际逻辑、解决关系、原理继承。不确定 → unrelated + 低 confidence。"""


def _pairs_from_evidence(rows: list[tuple[str, str, str]],
                         *, min_codocs: int = 2, top: int = 200
                         ) -> list[tuple[tuple[str, str], int]]:
    """(tech_id, doc_id, table) 行 → 共现对及计数(top N)。"""
    by_doc: dict[tuple[str, str], set[str]] = {}
    for tech_id, doc_id, table in rows:
        by_doc.setdefault((doc_id, table), set()).add(tech_id)
    cnt: dict[tuple[str, str], int] = {}
    for techs in by_doc.values():
        ordered = sorted(techs)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                p = (ordered[i], ordered[j])
                cnt[p] = cnt.get(p, 0) + 1
    ranked = sorted(((p, c) for p, c in cnt.items() if c >= min_codocs),
                    key=lambda kv: -kv[1])
    return ranked[:top]


async def build_llm_evolve_edges(db: AsyncSession, *, top_n: int = 200,
                                 min_codocs: int = 2) -> dict:
    """编排:共现对 → LLM 判向 → TECH_EVOLVE 边(conf 0.7·c)。"""
    rows = (await db.execute(
        select(TechEvidenceORM.tech_id, TechEvidenceORM.source_doc_id,
               TechEvidenceORM.source_table)
    )).all()
    pairs = _pairs_from_evidence(rows, min_codocs=min_codocs, top=top_n)
    if not pairs:
        return {"status": "done", "pairs": 0, "written": 0, "judged": 0}

    techs = {t.tech_id: t for t in (await db.execute(
        select(TechProfileORM).where(TechProfileORM.tech_layer == "CONCEPT")
    )).scalars().all()}
    gateway = LLMGateway()
    writer = TripleWriter(FoundationNeo4jRepo())
    judged = written = 0
    for (a_id, b_id), c in pairs:
        ta, tb = techs.get(a_id), techs.get(b_id)
        if not ta or not tb:
            continue
        na = ta.tech_name_cn or ta.tech_id
        nb = tb.tech_name_cn or tb.tech_id
        prompt = (f"技术 A:{na}\n技术 B:{nb}\n共现于 {c} 篇专利/论文"
                  f"(域:{ta.parent_ipc_code or tb.parent_ipc_code or '?'})\n"
                  f"请判断演进方向(judge_evolution)。")
        try:
            verdict, _ = await call_with_schema(
                gateway=gateway, model=settings.llm.agent_model,
                system_prompt=SYSTEM_PROMPT, user_prompt=prompt,
                function_name="judge_evolution",
                function_description="判断两技术概念的演进方向",
                output_schema=EvolveVerdict,
                caller="new_tech.evolve_llm",
            )
        except Exception as exc:  # noqa: BLE001  LLM 失败跳对
            logger.warning("evolve_llm_failed", a=na, b=nb, error=str(exc)[:80])
            continue
        judged += 1
        if verdict.direction not in ("A_to_B", "B_to_A"):
            continue
        sub, obj = (ta, tb) if verdict.direction == "A_to_B" else (tb, ta)
        triple = RelationTriple(
            subject_id=sub.tech_id, subject_type=EntityType.TECH,
            subject_name=sub.tech_name_cn or sub.tech_id,
            relation=RelationType.TECH_EVOLVE,
            object_id=obj.tech_id, object_type=EntityType.TECH,
            object_name=obj.tech_name_cn or obj.tech_id,
            evidence=f"LLM: {verdict.rationale[:200]}",
            confidence=round(0.7 * verdict.confidence, 4),
            source_doc_id=None,
            method=SourceMethod.LLM_ENRICH,
            extracted_at=datetime.now(UTC),
        )
        ok = await writer.write(triple)
        written += int(ok)
    logger.info("evolve_llm_done", pairs=len(pairs), judged=judged,
                written=written)
    return {"status": "done", "pairs": len(pairs), "judged": judged,
            "written": written}
