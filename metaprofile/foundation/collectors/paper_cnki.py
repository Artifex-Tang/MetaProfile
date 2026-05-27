"""
CNKI 知网论文采集适配器。

接口：CNKI Open API（机构授权，需 API Key）。
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

_BASE = settings.collectors.cnki_base_url


class CNKICollector(AbstractCollector):
    source = "cnki"
    doc_type = "paper"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.collectors.cnki_api_key}",
            "Accept": "application/json",
        }

    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:  # type: ignore[override]
        """
        检索接口：POST /v1/articles/search
        支持 TI（题名）、KW（关键词）、AB（摘要）复合检索。
        """
        page = 1
        page_size = 20
        collected = 0

        # 构建 CNKI 标准布尔检索式
        kw_expr = " OR ".join(f"KW='{kw}'" for kw in query.keywords)
        payload: dict[str, Any] = {
            "query": kw_expr,
            "page": page,
            "pageSize": page_size,
            "orderBy": "PubDate DESC",
        }
        if query.date_from:
            payload["pubDateFrom"] = query.date_from.strftime("%Y-%m-%d")
        if query.date_to:
            payload["pubDateTo"] = query.date_to.strftime("%Y-%m-%d")

        while collected < query.max_results:
            payload["page"] = page
            payload["pageSize"] = min(page_size, query.max_results - collected)

            resp = await self._post(
                f"{_BASE}/v1/articles/search",
                json=payload,
                headers=self._headers(),
            )
            data = resp.json()

            items: list[dict[str, Any]] = data.get("data", {}).get("list", [])
            if not items:
                break

            for item in items:
                yield RawDocument(
                    source=self.source,
                    doc_type=self.doc_type,
                    raw_id=item.get("dbCode", "") + "_" + item.get("filename", ""),
                    title=item.get("title"),
                    raw_data=item,
                    url=item.get("url"),
                )
                collected += 1
                if collected >= query.max_results:
                    return

            if len(items) < page_size:
                break
            page += 1

        logger.info("cnki_collect_done", keywords=query.keywords, count=collected)

    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        # raw_id 格式：{dbCode}_{filename}
        parts = raw_id.split("_", 1)
        if len(parts) != 2:
            return None
        db_code, filename = parts
        resp = await self._get(
            f"{_BASE}/v1/articles/detail",
            params={"dbCode": db_code, "filename": filename},
            headers=self._headers(),
        )
        data = resp.json().get("data")
        if not data:
            return None
        return RawDocument(
            source=self.source,
            doc_type=self.doc_type,
            raw_id=raw_id,
            title=data.get("title"),
            raw_data=data,
            url=data.get("url"),
        )
