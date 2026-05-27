"""
三重存储统一门面（Facade）。

将 PostgreSQL（结构化属性）+ Elasticsearch（全文/向量）+ Neo4j（关系图谱）
封装为单一接口，对上层只暴露"实体"概念。

一致性策略：
- PostgreSQL 写入失败 → 整体失败抛出
- ES / Neo4j 写入失败 → 记录到 entity_outbox，由独立 worker 重试
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from metaprofile.foundation.storage.es_repo import FoundationESRepo
from metaprofile.foundation.storage.neo4j_repo import FoundationNeo4jRepo
from metaprofile.foundation.storage.postgres_repo import PostgresRepo
from metaprofile.shared.schemas.base import EntityType

logger = structlog.get_logger(__name__)


@dataclass
class UnifiedRepo:
    """三重存储统一门面。"""

    postgres_repo: PostgresRepo
    es_repo: FoundationESRepo
    neo4j_repo: FoundationNeo4jRepo

    async def upsert_entity(
        self,
        *,
        entity_type: EntityType,
        entity_id: str,
        attributes: dict[str, Any],
        embedding: list[float] | None = None,
    ) -> None:
        # 强一致写 PostgreSQL
        await self.postgres_repo.upsert(entity_type, entity_id, attributes)

        # ES 最终一致写（失败入 outbox）
        try:
            await self.es_repo.upsert_entity(
                entity_type=entity_type,
                entity_id=entity_id,
                attributes=attributes,
                embedding=embedding,
            )
        except Exception as exc:
            logger.warning(
                "es_upsert_failed_will_retry",
                entity_id=entity_id,
                error=str(exc),
            )
            await self.postgres_repo.outbox_enqueue(
                target="es",
                entity_id=entity_id,
                entity_type=entity_type.value,
                payload={**attributes, "embedding": embedding} if embedding else attributes,
            )

        # Neo4j 最终一致写（失败入 outbox）
        try:
            await self.neo4j_repo.upsert_entity_node(
                entity_type, entity_id, attributes
            )
        except Exception as exc:
            logger.warning(
                "neo4j_upsert_failed_will_retry",
                entity_id=entity_id,
                error=str(exc),
            )
            await self.postgres_repo.outbox_enqueue(
                target="neo4j",
                entity_id=entity_id,
                entity_type=entity_type.value,
                payload=attributes,
            )

    async def get_entity(
        self, *, entity_type: EntityType, entity_id: str
    ) -> dict[str, Any] | None:
        """从 PostgreSQL 读取（单一可信源）。"""
        return await self.postgres_repo.find_by_id(entity_type, entity_id)

    async def delete_entity(
        self, *, entity_type: EntityType, entity_id: str
    ) -> bool:
        """从三库删除实体（PostgreSQL 同步，其余异步）。"""
        deleted = await self.postgres_repo.delete(entity_type, entity_id)
        if not deleted:
            return False

        try:
            await self.es_repo.delete_entity(entity_type, entity_id)
        except Exception as exc:
            logger.warning("es_delete_failed", entity_id=entity_id, error=str(exc))

        try:
            await self.neo4j_repo.delete_entity_node(entity_type, entity_id)
        except Exception as exc:
            logger.warning("neo4j_delete_failed", entity_id=entity_id, error=str(exc))

        return True
