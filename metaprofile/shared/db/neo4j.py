"""
Neo4j 5+ 异步驱动封装。

所有关系图谱操作通过此模块，禁止直接使用 neo4j driver。
"""
from __future__ import annotations

import json
import re
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
        """查询邻居节点。rel_types 为空时匹配所有关系类型。

        注意：变长路径 ``[r*1..N]`` 中 r 是 Relationship 的 **列表**，
        不能直接 ``type(r)``；depth=1 时改用单跳模式，r 为单个 Relationship。
        """
        if depth <= 1:
            rel_filter = f"[r:{'|'.join(rel_types)}]" if rel_types else "[r]"
        else:
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
    ) -> list[dict[str, Any]]:
        """最短路径查询，返回最多 5 条路径，每条 {nodes, rel_types}。

        nodes=节点 props 列表；rel_types=每跳关系类型（中文）。
        Cypher 不支持参数化变长边界，max_depth（已校验 int）直接拼入。
        """
        depth = int(max_depth)
        cypher = (
            "MATCH p=shortestPath("
            f"(a {{entity_id: $from_id}})-[*1..{depth}]-(b {{entity_id: $to_id}})"
            ") RETURN [n in nodes(p) | properties(n)] AS nodes, "
            "[r in relationships(p) | type(r)] AS rels LIMIT 5"
        )
        async with get_neo4j_session() as s:
            result = await s.run(cypher, from_id=from_id, to_id=to_id)
            rows = await result.data()
        return [{"nodes": row["nodes"], "rel_types": row["rels"]} for row in rows]

    async def find_related_chain(
        self,
        *,
        entity_id: str,
        label: str,
        rel_type: str,
        depth: int = 4,
        direction: str = "both",
    ) -> dict[str, Any]:
        """按关系类型 + 方向遍历 N 跳，返回 {nodes, edges}。

        direction ∈ {out, in, both}。rel_type 在本函数内校验必须为
        RelationType enum NAME 形式（仅 A-Z_，防 Cypher 注入，因其 backtick 拼入
        Cypher）；label/depth 直接拼 Cypher（Cypher 不支持参数化变长边界与关系
        类型占位）。去重 node/edge。
        """
        if not re.fullmatch(r"[A-Z_]+", rel_type):
            raise ValueError(
                f"invalid rel_type (must be enum name A-Z_): {rel_type!r}"
            )
        d = max(1, min(int(depth), 4))
        backtick = "`" + rel_type + "`"
        if direction == "out":
            pat = f"-[{backtick}*1..{d}]->"
        elif direction == "in":
            pat = f"<-[{backtick}*1..{d}]-"
        else:
            pat = f"-[{backtick}*1..{d}]-"
        cypher = (
            f"MATCH p=(n:{label} {{entity_id: $entity_id}}){pat}(m) "
            "RETURN [x in nodes(p) | properties(x)] AS nodes, "
            "[r in relationships(p) | {type: type(r), "
            "start: startNode(r).entity_id, end: endNode(r).entity_id}] AS rels "
            "LIMIT 200"
        )
        async with get_neo4j_session() as s:
            result = await s.run(cypher, entity_id=entity_id)
            rows = await result.data()
        nodes_map: dict[str, dict[str, Any]] = {}
        edges_seen: set[tuple[str, str, str]] = set()
        edges: list[dict[str, Any]] = []
        for row in rows:
            for nd in row["nodes"]:
                eid = nd.get("entity_id")
                if eid and eid not in nodes_map:
                    nodes_map[eid] = nd
            for r in row["rels"]:
                key = (r["start"], r["end"], r["type"])
                if key in edges_seen:
                    continue
                edges_seen.add(key)
                edges.append(
                    {"source": r["start"], "target": r["end"], "rel_type": r["type"]}
                )
        return {"nodes": list(nodes_map.values()), "edges": edges}

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
