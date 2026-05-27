"""
天眼查企业信息采集适配器。

接口：天眼查 Open API（商业授权，需 Token）。
文档类型：enterprise
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

_BASE = settings.collectors.tianyancha_base_url


class TianyanchaColl(AbstractCollector):
    source = "tianyancha"
    doc_type = "enterprise"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": settings.collectors.tianyancha_api_key,
            "Content-Type": "application/json",
        }

    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:  # type: ignore[override]
        """
        企业搜索：GET /v1/search?word=...
        天眼查 API 不支持批量关键词，逐关键词查询。
        """
        collected = 0

        for keyword in query.keywords:
            if collected >= query.max_results:
                break
            page_index = 1
            page_size = 20

            while collected < query.max_results:
                resp = await self._get(
                    f"{_BASE}/v1/search",
                    params={
                        "word": keyword,
                        "pageSize": min(page_size, query.max_results - collected),
                        "pageNum": page_index,
                    },
                    headers=self._headers(),
                )
                data = resp.json()
                if data.get("state") != "ok":
                    logger.warning(
                        "tianyancha_api_error",
                        keyword=keyword,
                        message=data.get("message"),
                    )
                    break

                items: list[dict[str, Any]] = data.get("data", {}).get("items", [])
                if not items:
                    break

                for item in items:
                    gid = str(item.get("id", ""))
                    yield RawDocument(
                        source=self.source,
                        doc_type=self.doc_type,
                        raw_id=gid,
                        title=item.get("name"),
                        raw_data=item,
                        url=f"https://www.tianyancha.com/company/{gid}",
                    )
                    collected += 1
                    if collected >= query.max_results:
                        return

                if len(items) < page_size:
                    break
                page_index += 1

        logger.info("tianyancha_collect_done", keywords=query.keywords, count=collected)

    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        resp = await self._get(
            f"{_BASE}/v1/companydetail/{raw_id}",
            headers=self._headers(),
        )
        data = resp.json()
        if data.get("state") != "ok":
            return None
        company = data.get("data", {})
        return RawDocument(
            source=self.source,
            doc_type=self.doc_type,
            raw_id=raw_id,
            title=company.get("name"),
            raw_data=company,
            url=f"https://www.tianyancha.com/company/{raw_id}",
        )
