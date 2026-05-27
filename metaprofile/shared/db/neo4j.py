"""
Neo4j 5+ 异步驱动封装。

所有关系图谱操作通过此模块，禁止直接使用 neo4j driver。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_driver: AsyncDriver | None = None


def get_neo4j_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password),
        )
    return _driver


@asynccontextmanager
async def get_neo4j_session() -> AsyncIterator[AsyncSession]:
    driver = get_neo4j_driver()
    async with driver.session(database=settings.neo4j.database) as session:
        yield session


class Neo4jRepo:
    """Neo4j 图谱操作封装。"""

    def __init__(self, driver: AsyncDriver | None = None) -> None:
        self._driver = driver or get_neo4j_driver()

    async def upsert_node(
        self,
        *,
        label: str,
        entity_id: str,
        props: dict[str, Any],
    ) -> None:
        """MERGE 节点（按 entity_id），然后 SET 属性。"""
        safe = _sanitize_props(props)
        cypher = (
            f"MERGE (n:{label} {{entity_id: $entity_id}}) "
            "SET n += $props"
        )
        async with get_neo4j_session() as s:
            await s.run(cypher, entity_id=entity_id, props=safe)

    async def upsert_relation(
        self,
        *,
        from_label: str,
        from_id: str,
        to_label: str,
        to_id: str,
        rel_type: str,
        props: dict[str, Any] | None = None,
    ) -> None:
        """MERGE 有向关系（两端节点必须已存在）。"""
        safe = _sanitize_props(props or {})
        cypher = (
            f"MATCH (a:{from_label} {{entity_id: $from_id}}) "
            f"MATCH (b:{to_label} {{entity_id: $to_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r += $props"
        )
        async with get_neo4j_session() as s:
            await s.run(cypher, from_id=from_id, to_id=to_id, props=safe)

    async def get_neighbors(
        self,
        *,
        entity_id: str,
        label: str,
        rel_types: list[str] | None = None,
        depth: int = 1,
    ) -> list[dict[str, Any]]:
        """查询邻居节点。rel_types 为空时匹配所有关系类型。"""
        rel_filter = (
            f"[r:{('|'.join(rel_types))}*1..{depth}]"
            if rel_types
            else f"[r*1..{depth}]"
        )
        cypher = (
            f"MATCH (n:{label} {{entity_id: $entity_id}})-{rel_filter}-(m) "
            "RETURN m, type(r) AS rel_type LIMIT 100"
        )
        async with get_neo4j_session() as s:
            result = await s.run(cypher, entity_id=entity_id)
            rows = await result.data()
        return [{"node": dict(row["m"]), "rel_type": row["rel_type"]} for row in rows]

    async def find_path(
        self,
        *,
        from_id: str,
        to_id: str,
        max_depth: int = 4,
    ) -> list[list[dict[str, Any]]]:
        """最短路径查询，返回最多 5 条路径，每条为节点列表。"""
        cypher = (
            "MATCH p=shortestPath("
            "(a {entity_id: $from_id})-[*1..$max_depth]-(b {entity_id: $to_id})"
            ") RETURN [n in nodes(p) | properties(n)] AS nodes LIMIT 5"
        )
        async with get_neo4j_session() as s:
            result = await s.run(cypher, from_id=from_id, to_id=to_id, max_depth=max_depth)
            rows = await result.data()
        return [row["nodes"] for row in rows]

    async def delete_node(self, *, label: str, entity_id: str) -> None:
        """删除节点及其所有关系。"""
        cypher = f"MATCH (n:{label} {{entity_id: $entity_id}}) DETACH DELETE n"
        async with get_neo4j_session() as s:
            await s.run(cypher, entity_id=entity_id)


def _sanitize_props(props: dict[str, Any]) -> dict[str, Any]:
    """Neo4j 属性值只允许基本类型，list/dict 序列化为 JSON 字符串。"""
    out: dict[str, Any] = {}
    for k, v in props.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, dict)):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = str(v)
    return out
