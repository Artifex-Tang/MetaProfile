"""
政府门户政策文件采集适配器。

策略：国务院/各部委网站全文检索接口（gov.cn 搜索 API）。
文档类型：policy
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

# 国务院门户网站搜索接口
_SEARCH_URL = "https://sousuo.www.gov.cn/sousuo/search.shtml"


class PolicyGovCollector(AbstractCollector):
    source = "policy_gov"
    doc_type = "policy"

    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:  # type: ignore[override]
        """
        gov.cn 搜索 API（GET 请求，返回 JSON）。
        dataTypeId=107 对应政策文件，107 为国务院政策，可按需扩展。
        """
        page = 1
        page_size = 10
        collected = 0
        kw = " ".join(query.keywords)

        while collected < query.max_results:
            params: dict[str, Any] = {
                "searchWord": kw,
                "dataTypeId": 107,
                "pageNow": page,
                "pageSize": min(page_size, query.max_results - collected),
            }
            if query.date_from:
                params["timeFiler"] = (
                    f"{query.date_from.strftime('%Y-%m-%d')}:{query.date_to.strftime('%Y-%m-%d')}"
                    if query.date_to
                    else f"{query.date_from.strftime('%Y-%m-%d')}:"
                )

            resp = await self._get(_SEARCH_URL, params=params)
            data = resp.json()

            items: list[dict[str, Any]] = data.get("searchVO", {}).get("categoryList", [{}])
            docs = items[0].get("listVO", []) if items else []
            if not docs:
                break

            for doc in docs:
                url = doc.get("url", "")
                raw_id = _extract_doc_id(url) or doc.get("id", url)
                yield RawDocument(
                    source=self.source,
                    doc_type=self.doc_type,
                    raw_id=raw_id,
                    title=doc.get("title"),
                    raw_data=doc,
                    url=url,
                )
                collected += 1
                if collected >= query.max_results:
                    return

            total = data.get("searchVO", {}).get("total", 0)
            if collected >= total or len(docs) < page_size:
                break
            page += 1

        logger.info("policy_gov_collect_done", keywords=query.keywords, count=collected)

    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        # 政策文件没有通用详情 API，通过 URL 直接抓取
        url = raw_id if raw_id.startswith("http") else f"https://www.gov.cn/zhengce/{raw_id}.htm"
        resp = await self._get(url)
        return RawDocument(
            source=self.source,
            doc_type=self.doc_type,
            raw_id=raw_id,
            raw_data={"html": resp.text[:50000]},  # 截断保存原始 HTML
            url=url,
        )


def _extract_doc_id(url: str) -> str | None:
    """从 gov.cn URL 中提取文档 ID。"""
    import re

    m = re.search(r"/(\d{4}-\d{2}/\d{2}/content_\d+)\.htm", url)
    return m.group(1).replace("/", "_") if m else None
