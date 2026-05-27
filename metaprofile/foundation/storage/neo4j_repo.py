"""
Neo4j Repository（foundation 层封装）。

对 shared.db.Neo4jRepo 做实体语义封装：
- 节点 label 与 EntityType 对应（TECH / ORG / PERSON / PROJECT）
- 关系类型来自 shared.schemas.relations.RelationType
"""
from __future__ import annotations

from typing import Any

import structlog

from metaprofile.shared.db.neo4j import Neo4jRepo
from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.schemas.relations import RelationTriple

logger = structlog.get_logger(__name__)

# EntityType → Neo4j label 映射（保持大写以匹配 RelationTriple）
_ENTITY_LABELS: dict[EntityType, str] = {
    EntityType.TECH: "Tech",
    EntityType.ORG: "Org",
    EntityType.PERSON: "Person",
    EntityType.PROJECT: "Project",
}


class FoundationNeo4jRepo:
    """Foundation 层 Neo4j Repository。"""

    def __init__(self, repo: Neo4jRepo | None = None) -> None:
        self._repo = repo or Neo4jRepo()

    def label(self, entity_type: EntityType) -> str:
        return _ENTITY_LABELS[entity_type]

    async def upsert_node(
        self,
        *,
        label: str,
        entity_id: str,
        props: dict[str, Any],
    ) -> None:
        """兼容 unified_repo 的直接调用签名。"""
        await self._repo.upsert_node(label=label, entity_id=entity_id, props=props)

    async def upsert_entity_node(
        self,
        entity_type: EntityType,
        entity_id: str,
        props: dict[str, Any],
    ) -> None:
        """实体节点语义 upsert（自动推断 label）。"""
        await self._repo.upsert_node(
            label=self.label(entity_type),
            entity_id=entity_id,
            props=props,
        )

    async def write_relation(self, triple: RelationTriple) -> None:
        """写入关系三元组。两端节点必须已存在。"""
        await self._repo.upsert_relation(
            from_label=self.label(triple.subject_type),
            from_id=triple.subject_id,
            to_label=self.label(triple.object_type),
            to_id=triple.object_id,
            rel_type=triple.relation.value,
            props={
                "confidence": triple.confidence,
                "method": triple.method.value,
                "source_doc_id": triple.source_doc_id or "",
                "evidence": triple.evidence or "",
            },
        )

    async def get_entity_relations(
        self,
        entity_type: EntityType,
        entity_id: str,
        *,
        rel_types: list[str] | None = None,
        depth: int = 1,
    ) -> list[dict[str, Any]]:
        return await self._repo.get_neighbors(
            entity_id=entity_id,
            label=self.label(entity_type),
            rel_types=rel_types,
            depth=depth,
        )

    async def find_path(
        self,
        *,
        from_entity_id: str,
        to_entity_id: str,
        max_depth: int = 4,
    ) -> list[list[dict[str, Any]]]:
        return await self._repo.find_path(
            from_id=from_entity_id,
            to_id=to_entity_id,
            max_depth=max_depth,
        )

    async def delete_entity_node(
        self, entity_type: EntityType, entity_id: str
    ) -> None:
        await self._repo.delete_node(
            label=self.label(entity_type), entity_id=entity_id
        )
