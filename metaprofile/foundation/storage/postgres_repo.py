"""
PostgreSQL Repository（foundation 层泛型存储）。

使用 JSONB 泛型存储，不依赖 profile_xxx 的 typed ORM 模型。
这样 foundation 层与 profile 层无耦合，符合三层架构职责划分。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.foundation.storage.orm_models import EntityOutboxORM, EntityStoreORM
from metaprofile.shared.schemas.base import EntityType

logger = structlog.get_logger(__name__)


class PostgresRepo:
    """Foundation 层 PostgreSQL Repository。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        entity_type: EntityType,
        entity_id: str,
        attributes: dict[str, Any],
    ) -> None:
        """INSERT ... ON CONFLICT(entity_id) DO UPDATE data = EXCLUDED.data。"""
        stmt = (
            insert(EntityStoreORM)
            .values(
                entity_type=entity_type.value,
                entity_id=entity_id,
                data=attributes,
            )
            .on_conflict_do_update(
                index_elements=["entity_id"],
                set_={
                    "data": attributes,
                    "entity_type": entity_type.value,
                    "updated_at": func_now(),
                },
            )
        )
        await self._session.execute(stmt)

    async def find_by_id(
        self,
        entity_type: EntityType,
        entity_id: str,
    ) -> dict[str, Any] | None:
        """按 entity_id 查询（校验 entity_type 防止跨类型碰撞）。"""
        stmt = select(EntityStoreORM).where(
            EntityStoreORM.entity_id == entity_id,
            EntityStoreORM.entity_type == entity_type.value,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return dict(row.data) if row is not None else None

    async def list_by_type(
        self,
        entity_type: EntityType,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(EntityStoreORM)
            .where(EntityStoreORM.entity_type == entity_type.value)
            .order_by(EntityStoreORM.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [dict(row.data) for row in result.scalars()]

    async def delete(self, entity_type: EntityType, entity_id: str) -> bool:
        """删除实体，返回是否实际删除（False = 原本不存在）。"""
        stmt = select(EntityStoreORM).where(
            EntityStoreORM.entity_id == entity_id,
            EntityStoreORM.entity_type == entity_type.value,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        return True

    async def count(self, entity_type: EntityType) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(EntityStoreORM).where(
            EntityStoreORM.entity_type == entity_type.value
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ─── Outbox ─────────────────────────────────────────────────────────────

    async def outbox_enqueue(
        self,
        *,
        target: str,
        entity_id: str,
        payload: dict[str, Any],
        entity_type: str = "",
    ) -> None:
        """向 outbox 队列添加一条待重试任务。"""
        record = EntityOutboxORM(
            target=target,
            entity_id=entity_id,
            entity_type=entity_type,
            payload=payload,
            status="pending",
        )
        self._session.add(record)
        logger.debug(
            "outbox_enqueued",
            target=target,
            entity_id=entity_id,
        )

    async def outbox_pop_pending(
        self,
        *,
        target: str,
        batch_size: int = 50,
    ) -> list[EntityOutboxORM]:
        """取出一批 pending 任务（FOR UPDATE SKIP LOCKED 防止并发重复消费）。"""
        from sqlalchemy import and_

        stmt = (
            select(EntityOutboxORM)
            .where(
                and_(
                    EntityOutboxORM.target == target,
                    EntityOutboxORM.status == "pending",
                )
            )
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def outbox_mark_done(self, record_id: int) -> None:
        stmt = (
            update(EntityOutboxORM)
            .where(EntityOutboxORM.id == record_id)
            .values(status="done", processed_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def outbox_mark_failed(self, record_id: int, error: str) -> None:
        stmt = (
            update(EntityOutboxORM)
            .where(EntityOutboxORM.id == record_id)
            .values(
                status="failed",
                error_message=error[:512],
                retry_count=EntityOutboxORM.retry_count + 1,
            )
        )
        await self._session.execute(stmt)


def func_now():
    from sqlalchemy import func

    return func.now()
