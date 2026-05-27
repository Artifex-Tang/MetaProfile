"""
实体/文档计数器。

查询 PostgreSQL entity_store 获取各实体类型数量。
查询 entity_outbox 获取待处理任务数。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metaprofile.shared.schemas.base import EntityType


@dataclass
class EntityCounts:
    by_type: dict[str, int] = field(default_factory=dict)   # EntityType.value → count
    total: int = 0


@dataclass
class OutboxCounts:
    pending: int = 0
    failed: int = 0


class EntityCounter:
    """
    从 PostgresRepo 统计实体数量。

    Args:
        postgres_repo: PostgresRepo 实例
    """

    def __init__(self, postgres_repo: Any) -> None:
        self._pg = postgres_repo

    async def count_by_type(self) -> EntityCounts:
        """统计各实体类型数量。"""
        counts: dict[str, int] = {}
        total = 0
        for et in EntityType:
            n = await self._pg.count(et)
            counts[et.value] = n
            total += n
        return EntityCounts(by_type=counts, total=total)

    async def count_outbox(self) -> OutboxCounts:
        """统计 outbox 待处理 / 失败数量。"""
        try:
            pending = await self._pg.outbox_count_by_status("pending")
            failed = await self._pg.outbox_count_by_status("failed")
        except AttributeError:
            # outbox_count_by_status 可能未实现（向后兼容）
            return OutboxCounts()
        return OutboxCounts(pending=pending, failed=failed)

    async def count_entity_type(self, entity_type: EntityType) -> int:
        """单实体类型计数。"""
        return await self._pg.count(entity_type)
