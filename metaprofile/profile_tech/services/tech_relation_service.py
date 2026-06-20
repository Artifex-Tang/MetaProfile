"""技术画像关系服务（基于 Neo4j）。"""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_tech.schemas.response import (
    RelationItem,
    RelationList,
    RelationPathResult,
    RelationPathStep,
    TechRelationEdge,
    TechRelationNode,
    TechRelationResult,
)
from metaprofile.shared.db.neo4j import Neo4jRepo

logger = structlog.get_logger(__name__)


class TechRelationService:
    def __init__(self) -> None:
        self._neo4j = Neo4jRepo()

    async def list_relations(
        self,
        session: AsyncSession,
        *,
        tech_id: str,
        relation_type: str | None,
        limit: int,
    ) -> RelationList:
        rel_types = [relation_type] if relation_type else None
        rows = await self._neo4j.get_neighbors(
            entity_id=tech_id,
            label="Tech",
            rel_types=rel_types,
            depth=1,
        )
        items = [
            RelationItem(
                relation_type=row["rel_type"],
                target_entity_id=row["node"].get("entity_id", ""),
                target_entity_type=row["node"].get("entity_type", ""),
                target_name=(
                    row["node"].get("name")
                    or row["node"].get("tech_name_cn")
                    or row["node"].get("entity_id", "")
                ),
                confidence=float(row["node"].get("confidence", 0.0)),
                evidence=row["node"].get("evidence"),
            )
            for row in rows[:limit]
        ]
        return RelationList(items=items, total=len(items))

    async def find_path(
        self, *, from_id: str, to_id: str, max_depth: int
    ) -> RelationPathResult:
        paths_raw = await self._neo4j.find_path(
            from_id=from_id, to_id=to_id, max_depth=max_depth
        )
        if not paths_raw:
            return RelationPathResult(found=False, paths=[])

        def _name(node: dict) -> str | None:
            return (
                node.get("name")
                or node.get("tech_name_cn")
                or node.get("entity_id")
            )

        paths = []
        for p in paths_raw:
            nodes = p["nodes"]
            rels = p["rel_types"]
            steps = [
                RelationPathStep(
                    from_id=nodes[i].get("entity_id", ""),
                    from_name=_name(nodes[i]),
                    from_type=nodes[i].get("entity_type"),
                    relation=rels[i] if i < len(rels) else "RELATED",
                    to_id=nodes[i + 1].get("entity_id", ""),
                    to_name=_name(nodes[i + 1]),
                    to_type=nodes[i + 1].get("entity_type"),
                )
                for i in range(len(nodes) - 1)
            ]
            if steps:
                paths.append(steps)
        return RelationPathResult(found=bool(paths), paths=paths)

    async def find_tech_relation(
        self, *, tech_id: str, viewpoint: str, depth: int
    ) -> TechRelationResult:
        # viewpoint → 关系类型（用枚举 NAME，与 mock 一致：Neo4j 存枚举名如 TECH_EVOLVE）；
        # 非法 viewpoint 默认 evolve。见 RelationType / gen_mock_data.rel()。
        from metaprofile.shared.schemas.relations import RelationType

        if viewpoint == "prereq":
            rel_type, vp = RelationType.TECH_PREREQ.name, "prereq"
        else:
            rel_type, vp = RelationType.TECH_EVOLVE.name, "evolve"
        raw = await self._neo4j.find_related_chain(
            entity_id=tech_id,
            label="Tech",
            rel_type=rel_type,
            depth=depth,
            direction="both",
        )

        def _name(n: dict) -> str | None:
            return n.get("name") or n.get("tech_name_cn") or n.get("entity_id")

        nodes = [
            TechRelationNode(
                entity_id=n.get("entity_id", ""),
                entity_type=n.get("entity_type"),
                name=_name(n),
            )
            for n in raw["nodes"]
        ]
        edges = [TechRelationEdge(**e) for e in raw["edges"]]
        return TechRelationResult(nodes=nodes, edges=edges, viewpoint=vp)
