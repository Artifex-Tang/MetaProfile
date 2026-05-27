"""
WIPO PatentScope 采集适配器。

接口：WIPO PatentScope REST API v1（公开免费，无需 Key，有速率限制）。
文档类型：patent
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import structlog

from metaprofile.foundation.collectors.base import (
    AbstractCollector,
    CollectQuery,
    RawDocument,
)
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_BASE = "https://patentscope.wipo.int/search/en/rest"


class WIPOCollector(AbstractCollector):
    source = "wipo"
    doc_type = "patent"

    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:  # type: ignore[override]
        """
        WIPO PatentScope 简单检索：GET /search?query=...&office=...
        返回 IPC 国际专利。
        """
        offset = 0
        page_size = 20
        collected = 0
        query_str = " OR ".join(query.keywords)

        params: dict[str, Any] = {
            "query": query_str,
            "offset": offset,
            "limit": page_size,
            "lang": "EN",
        }
        if query.date_from:
            params["dateFrom"] = query.date_from.isoformat()
        if query.date_to:
            params["dateTo"] = query.date_to.isoformat()

        while collected < query.max_results:
            params["offset"] = offset
            params["limit"] = min(page_size, query.max_results - collected)

            resp = await self._get(f"{_BASE}/search", params=params)
            data = resp.json()

            results: list[dict[str, Any]] = data.get("results", [])
            if not results:
                break

            for item in results:
                pub_num = item.get("publicationNumber", "")
                yield RawDocument(
                    source=self.source,
                    doc_type=self.doc_type,
                    raw_id=pub_num,
                    title=item.get("title"),
                    raw_data=item,
                    url=f"https://patentscope.wipo.int/search/en/detail.jsf?docId={pub_num}",
                    lang="en",
                )
                collected += 1
                if collected >= query.max_results:
                    return

            if len(results) < page_size:
                break
            offset += page_size

        logger.info("wipo_collect_done", keywords=query.keywords, count=collected)

    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        resp = await self._get(f"{_BASE}/patent/{raw_id}")
        data = resp.json()
        if not data:
            return None
        return RawDocument(
            source=self.source,
            doc_type=self.doc_type,
            raw_id=raw_id,
            title=data.get("title"),
            raw_data=data,
            url=f"https://patentscope.wipo.int/search/en/detail.jsf?docId={raw_id}",
            lang="en",
        )
