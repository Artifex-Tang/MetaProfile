"""
采集器抽象基类 + 公共数据模型。

所有外部数据源采集适配器继承 AbstractCollector，
输出统一的 RawDocument，后续进入 cleaners 管道。
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any

import httpx
import structlog
from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import ProfileBase

logger = structlog.get_logger(__name__)


# ─── 公共数据模型 ────────────────────────────────────────────────────────────

class CollectQuery(ProfileBase):
    """采集查询参数。"""

    keywords: list[str] = Field(..., min_length=1)
    date_from: date | None = None
    date_to: date | None = None
    max_results: int = Field(default=100, ge=1, le=10000)
    extra: dict[str, Any] = Field(default_factory=dict)


class RawDocument(ProfileBase):
    """原始采集文档（未经清洗）。所有采集器的统一输出格式。"""

    source: str             # 'cnipa' | 'wipo' | 'cnki' | 'wos' | 'nsfc' | ...
    doc_type: str           # 'patent' | 'paper' | 'project' | 'enterprise' | 'policy' | 'tender'
    raw_id: str             # 来源系统内的原始 ID（专利号/论文 ID/项目编号等）
    title: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    url: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lang: str = "zh"        # 'zh' | 'en'


class CollectError(Exception):
    """采集过程中不可重试的错误（如鉴权失败、资源不存在）。"""


class CollectRateLimitError(Exception):
    """被限流，可以重试。"""


# ─── 抽象基类 ────────────────────────────────────────────────────────────────

class AbstractCollector(ABC):
    """所有外部数据源采集适配器必须继承此类。"""

    source: str   # 子类必须设置
    doc_type: str

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or self._default_client()
        self._rps = settings.collectors.rate_limit_rps
        self._last_request_time: float = 0.0

    def _default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=settings.collectors.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": "MetaProfile/1.0 research-crawler"},
        )

    async def _throttle(self) -> None:
        """简单令牌桶限速：保证相邻请求间隔 >= 1/rps 秒。"""
        import time

        now = time.monotonic()
        min_interval = 1.0 / self._rps
        elapsed = now - self._last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.monotonic()

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """带限速的 GET 请求（含自动重试）。"""
        await self._throttle()
        for attempt in range(settings.collectors.max_retries):
            try:
                resp = await self._client.get(url, **kwargs)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", "5"))
                    logger.warning("rate_limited", url=url, wait_seconds=wait)
                    await asyncio.sleep(wait)
                    raise CollectRateLimitError(f"Rate limited on {url}")
                resp.raise_for_status()
                return resp
            except CollectRateLimitError:
                if attempt == settings.collectors.max_retries - 1:
                    raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    raise CollectError(f"Auth error on {url}: {exc}") from exc
                if attempt == settings.collectors.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        raise CollectError(f"Exhausted retries for {url}")  # unreachable but satisfies type

    async def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        await self._throttle()
        for attempt in range(settings.collectors.max_retries):
            try:
                resp = await self._client.post(url, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    raise CollectError(f"Auth error on {url}: {exc}") from exc
                if attempt == settings.collectors.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        raise CollectError(f"Exhausted retries for {url}")

    @abstractmethod
    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:
        """流式采集。子类实现，yield RawDocument。"""

    @abstractmethod
    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        """按原始 ID 获取单条文档。"""

    async def aclose(self) -> None:
        await self._client.aclose()
