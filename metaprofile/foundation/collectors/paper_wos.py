"""
Web of Science (Clarivate) 论文采集适配器。

接口：WoS Starter API v1（需机构 API Key）。
文档类型：paper
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

_BASE = settings.collectors.wos_base_url


class WoSCollector(AbstractCollector):
    source = "wos"
    doc_type = "paper"

    def _headers(self) -> dict[str, str]:
        return {
            "X-ApiKey": settings.collectors.wos_api_key,
            "Accept": "application/json",
        }

    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:  # type: ignore[override]
        """
        WoS Starter API：GET /documents
        查询语法：TS=（topic search，含题名/摘要/关键词）
        """
        page = 1
        page_size = 10  # WoS Starter API 单次最多 10 条
        collected = 0

        ts_query = " OR ".join(f'TS="{kw}"' for kw in query.keywords)
        params: dict[str, Any] = {
            "q": ts_query,
            "limit": page_size,
            "page": page,
            "sortField": "PY+D",  # 按年份降序
        }
        if query.date_from and query.date_to:
            params["publishTimeSpan"] = (
                f"{query.date_from.strftime('%Y-%m-%d')}+{query.date_to.strftime('%Y-%m-%d')}"
            )

        while collected < query.max_results:
            params["page"] = page
            params["limit"] = min(page_size, query.max_results - collected)

            resp = await self._get(
                f"{_BASE}/documents",
                params=params,
                headers=self._headers(),
            )
            data = resp.json()

            hits: list[dict[str, Any]] = data.get("hits", [])
            if not hits:
                break

            for hit in hits:
                uid = hit.get("uid", "")
                title_obj = hit.get("title", {})
                title = (
                    title_obj.get("value")
                    if isinstance(title_obj, dict)
                    else str(title_obj)
                )
                yield RawDocument(
                    source=self.source,
                    doc_type=self.doc_type,
                    raw_id=uid,
                    title=title,
                    raw_data=hit,
                    url=f"https://www.webofscience.com/wos/woscc/full-record/{uid}",
                    lang="en",
                )
                collected += 1
                if collected >= query.max_results:
                    return

            total = data.get("metadata", {}).get("total", 0)
            if collected >= total or len(hits) < page_size:
                break
            page += 1

        logger.info("wos_collect_done", keywords=query.keywords, count=collected)

    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        resp = await self._get(
            f"{_BASE}/documents/{raw_id}",
            headers=self._headers(),
        )
        data = resp.json()
        if not data:
            return None
        title_obj = data.get("title", {})
        title = title_obj.get("value") if isinstance(title_obj, dict) else str(title_obj)
        return RawDocument(
            source=self.source,
            doc_type=self.doc_type,
            raw_id=raw_id,
            title=title,
            raw_data=data,
            url=f"https://www.webofscience.com/wos/woscc/full-record/{raw_id}",
            lang="en",
        )
