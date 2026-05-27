"""
Redis 7+ 异步客户端。

用途：画像缓存、任务幂等锁。
Key 命名空间：metaprofile:{entity_type}:{entity_id}
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_pool: aioredis.ConnectionPool | None = None


def get_redis_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            str(settings.redis.dsn),
            decode_responses=True,
            max_connections=50,
        )
    return _pool


def get_redis() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=get_redis_pool())


class CacheClient:
    """业务级缓存客户端。"""

    DEFAULT_TTL = 3600

    def __init__(self, r: aioredis.Redis | None = None) -> None:
        self._r = r or get_redis()

    @staticmethod
    def _key(entity_type: str, entity_id: str) -> str:
        return f"metaprofile:{entity_type}:{entity_id}"

    async def get(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        raw = await self._r.get(self._key(entity_type, entity_id))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def set(
        self,
        entity_type: str,
        entity_id: str,
        data: dict[str, Any],
        ttl: int = DEFAULT_TTL,
    ) -> None:
        await self._r.setex(
            self._key(entity_type, entity_id),
            ttl,
            json.dumps(data, ensure_ascii=False),
        )

    async def delete(self, entity_type: str, entity_id: str) -> None:
        await self._r.delete(self._key(entity_type, entity_id))

    async def invalidate_pattern(self, pattern: str) -> int:
        """按 pattern 批量删除（谨慎使用，生产环境用 SCAN 替代 KEYS）。"""
        keys: list[str] = []
        async for key in self._r.scan_iter(match=pattern, count=100):
            keys.append(key)
        if not keys:
            return 0
        return await self._r.delete(*keys)

    @asynccontextmanager
    async def lock(self, key: str, timeout: int = 30) -> AsyncIterator[bool]:
        """简单分布式锁。acquired=False 时调用方自行决定是否跳过。"""
        lock_key = f"metaprofile:lock:{key}"
        acquired = await self._r.set(lock_key, "1", nx=True, ex=timeout)
        try:
            yield bool(acquired)
        finally:
            if acquired:
                await self._r.delete(lock_key)
