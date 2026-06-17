"""
关系三元组写入器。

将 RelationTriple 写入 Neo4j（经 FoundationNeo4jRepo）。
批量写入时按 source_doc_id 分组，便于溯源。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from metaprofile.shared.schemas.relations import RelationTriple

logger = logging.getLogger(__name__)

_ENTITY_LABELS: dict[str, str] = {
    "TECH": "Tech",
    "ORG": "Org",
    "PERSON": "Person",
    "PROJECT": "Project",
    # 卫星实体(关系端点,非画像类型)
    "STRATEGY": "Strategy",
    "EVENT": "Event",
    "ENTERPRISE": "Enterprise",
    "CONTRACT": "Contract",
    "PACKAGE": "Package",
}


@dataclass
class WriteStats:
    written: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class TripleWriter:
    """将 RelationTriple 列表持久化到 Neo4j。"""

    def __init__(self, neo4j_repo: object) -> None:
        # neo4j_repo: FoundationNeo4jRepo（用 object 避免循环导入）
        self._neo4j = neo4j_repo

    async def write(self, triple: RelationTriple) -> bool:
        """写入单条三元组。Returns True on success."""
        try:
            await self._write_one(triple)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "triple write failed: %s->%s [%s]: %s",
                triple.subject_id,
                triple.object_id,
                triple.relation,
                exc,
            )
            return False

    async def write_batch(self, triples: list[RelationTriple]) -> WriteStats:
        """批量写入，收集统计信息。"""
        stats = WriteStats()
        for triple in triples:
            ok = await self.write(triple)
            if ok:
                stats.written += 1
            else:
                stats.failed += 1
                stats.errors.append(
                    f"{triple.subject_id}-[{triple.relation}]->{triple.object_id}"
                )
        return stats

    async def _write_one(self, triple: RelationTriple) -> None:
        subj_label = _ENTITY_LABELS.get(triple.subject_type.value, "Entity")
        obj_label = _ENTITY_LABELS.get(triple.object_type.value, "Entity")

        props: dict = {
            "confidence": triple.confidence,
            "method": triple.method.value,
            "extracted_at": triple.extracted_at.isoformat(),
        }
        if triple.evidence:
            props["evidence"] = triple.evidence[:500]  # cap evidence length
        if triple.source_doc_id:
            props["source_doc_id"] = triple.source_doc_id

        await self._neo4j._repo.upsert_relation(
            from_label=subj_label,
            from_id=triple.subject_id,
            to_label=obj_label,
            to_id=triple.object_id,
            rel_type=triple.relation.value,
            props=props,
        )
