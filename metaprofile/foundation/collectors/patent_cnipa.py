"""
国知局（CNIPA）专利采集适配器。

接口：CNIPA 专利检索系统 REST API（需 API Key）。
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

_BASE = settings.collectors.cnipa_base_url


class CNIPACollector(AbstractCollector):
    source = "cnipa"
    doc_type = "patent"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.collectors.cnipa_api_key}",
            "Content-Type": "application/json",
        }

    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:  # type: ignore[override]
        """
        全文检索接口：POST /pss/rest/query
        支持关键词、日期范围，分页 page_size=20。
        """
        page = 1
        page_size = 20
        collected = 0

        while collected < query.max_results:
            payload: dict[str, Any] = {
                "query": " OR ".join(f'"{kw}"' for kw in query.keywords),
                "pageNum": page,
                "pageSize": min(page_size, query.max_results - collected),
                "sortField": "AD",
                "sortType": "desc",
            }
            if query.date_from:
                payload["dateFrom"] = query.date_from.strftime("%Y%m%d")
            if query.date_to:
                payload["dateTo"] = query.date_to.strftime("%Y%m%d")

            resp = await self._post(
                f"{_BASE}/pss/rest/query",
                json=payload,
                headers=self._headers(),
            )
            data = resp.json()

            hits: list[dict[str, Any]] = data.get("data", {}).get("hits", [])
            if not hits:
                break

            for hit in hits:
                yield RawDocument(
                    source=self.source,
                    doc_type=self.doc_type,
                    raw_id=hit.get("ANE", hit.get("appNumber", "")),
                    title=hit.get("TI") or hit.get("title"),
                    raw_data=hit,
                    url=f"{_BASE}/patent/query?appNumber={hit.get('ANE', '')}",
                )
                collected += 1
                if collected >= query.max_results:
                    return

            if len(hits) < page_size:
                break
            page += 1

        logger.info("cnipa_collect_done", keywords=query.keywords, count=collected)

    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        resp = await self._get(
            f"{_BASE}/pss/rest/detail",
            params={"appNumber": raw_id},
            headers=self._headers(),
        )
        data = resp.json().get("data")
        if not data:
            return None
        return RawDocument(
            source=self.source,
            doc_type=self.doc_type,
            raw_id=raw_id,
            title=data.get("TI"),
            raw_data=data,
            url=f"{_BASE}/patent/query?appNumber={raw_id}",
        )
