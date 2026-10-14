"""tech-tech 真挖掘(Phase E4/E5):共现网 + 时序演进链。

E4 TECH_CO_OCCURS:tech_evidence 同文档 ≥min_codocs 的 L2 概念对 → 共现边
   (confidence=共现数归一,method=RULE)。
E5 TECH_EVOLVE(v1 时序版):同 parent_ipc 域内 L2 概念按首现年排序 →
   相邻概念链边(低置信 0.3,IPC 共类时序兜底;LLM problem-solution 升级留口)。

写入走 TripleWriter(枚举 VALUE,与 TECH_CONTAINS 真挖边一致)。
"""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.foundation.relation.triple_writer import TripleWriter
from metaprofile.foundation.storage.neo4j_repo import FoundationNeo4jRepo
from metaprofile.ingest_ods.domain.orm_models import TechEvidenceORM
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple, RelationType

logger = structlog.get_logger(__name__)


def _triple(sub_id: str, sub_name: str, rel: RelationType,
            obj_id: str, obj_name: str, *, confidence: float,
            evidence: str | None) -> RelationTriple:
    return RelationTriple(
        subject_id=sub_id, subject_type=EntityType.TECH, subject_name=sub_name,
        relation=rel,
        object_id=obj_id, object_type=EntityType.TECH, object_name=obj_name,
        evidence=evidence, confidence=confidence, source_doc_id=None,
        method=SourceMethod.RULE, extracted_at=datetime.now(UTC),
    )


async def build_cooccurrence_edges(
    db: AsyncSession, *, min_codocs: int = 3, top: int = 2000,
) -> dict:
    """同文档 L2 共现对 → TECH_CO_OCCURS 边(按共现数取 top)。"""
    rows = (await db.execute(
        select(
            TechEvidenceORM.source_doc_id,
            TechEvidenceORM.source_table,
            TechEvidenceORM.tech_id,
        )
    )).all()
    by_doc: dict[tuple[str, str], set[str]] = {}
    for doc_id, table, tech_id in rows:
        by_doc.setdefault((doc_id, table), set()).add(tech_id)
    pair_count: dict[tuple[str, str], int] = {}
    for techs in by_doc.values():
        ordered = sorted(techs)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                pair_count[(ordered[i], ordered[j])] = (
                    pair_count.get((ordered[i], ordered[j]), 0) + 1
                )
    strong = {p: c for p, c in pair_count.items() if c >= min_codocs}
    top_pairs = sorted(strong.items(), key=lambda kv: -kv[1])[:top]
    if not top_pairs:
        return {"status": "done", "pairs": 0, "written": 0}

    names = {t.tech_id: (t.tech_name_cn or t.tech_name_en or t.tech_id)
             for t in (await db.execute(select(TechProfileORM))).scalars().all()}
    max_c = top_pairs[0][1]
    writer = TripleWriter(FoundationNeo4jRepo())
    triples = [
        _triple(a, names.get(a, a), RelationType.TECH_CO_OCCURS,
                b, names.get(b, b),
                confidence=round(c / max_c, 4),
                evidence=f"共现文档数 {c}")
        for (a, b), c in top_pairs
    ]
    stats = await writer.write_batch(triples)
    logger.info("tech_cooccurs_built", pairs=len(top_pairs),
                written=stats.written, failed=stats.failed)
    return {"status": "done", "pairs": len(top_pairs), "written": stats.written}


async def build_temporal_evolve_edges(
    db: AsyncSession, *, per_domain_cap: int = 60,
) -> dict:
    """同 parent_ipc 域内按首现证据序 → 相邻 L2 概念 TECH_EVOLVE 链(v1 时序版)。"""
    l2 = (await db.execute(
        select(TechProfileORM)
        .where(TechProfileORM.tech_layer == "CONCEPT")
        .order_by(TechProfileORM.tech_id)
    )).scalars().all()
    ev_rows = (await db.execute(
        select(TechEvidenceORM.tech_id, TechEvidenceORM.id)
    )).all()
    first_ev: dict[str, int] = {}
    for tech_id, ev_id in ev_rows:
        if tech_id not in first_ev or ev_id < first_ev[tech_id]:
            first_ev[tech_id] = ev_id

    domains: dict[str, list[TechProfileORM]] = {}
    for t in l2:
        if t.parent_ipc_code:
            domains.setdefault(t.parent_ipc_code, []).append(t)

    triples: list[RelationTriple] = []
    for sub, concepts in domains.items():
        ranked = sorted(
            concepts,
            key=lambda t: (first_ev.get(t.tech_id, 10**12), t.tech_id),
        )[:per_domain_cap]
        for a, b in zip(ranked, ranked[1:], strict=False):
            triples.append(_triple(
                a.tech_id, a.tech_name_cn or a.tech_id,
                RelationType.TECH_EVOLVE,
                b.tech_id, b.tech_name_cn or b.tech_id,
                confidence=0.3,
                evidence=f"同 IPC 域 {sub} 证据时序相邻(v1 启发式,非 problem-solution)",
            ))
    if not triples:
        return {"status": "done", "chains": 0, "written": 0}
    writer = TripleWriter(FoundationNeo4jRepo())
    stats = await writer.write_batch(triples)
    logger.info("tech_evolve_built", chains=len(triples),
                written=stats.written, failed=stats.failed)
    return {"status": "done", "chains": len(triples), "written": stats.written}
