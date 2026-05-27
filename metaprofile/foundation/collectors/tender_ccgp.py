"""
中国政府采购网（CCGP）招投标信息采集适配器。

接口：CCGP 公告检索接口（POST JSON）。
文档类型：tender
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

_SEARCH_URL = f"{settings.collectors.ccgp_base_url}/internet/publicInfo/pubInfoDetailList.do"
_DETAIL_URL = f"{settings.collectors.ccgp_base_url}/internet/publicInfo/pubInfoDetail.do"


class CCGPCollector(AbstractCollector):
    source = "ccgp"
    doc_type = "tender"

    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:  # type: ignore[override]
        """
        CCGP 公告检索（支持采购需求/项目名称关键词检索）。
        noticeType=1000（招标公告），可扩展为 2000（中标公告）等。
        """
        page = 1
        page_size = 20
        collected = 0

        for keyword in query.keywords:
            if collected >= query.max_results:
                break
            page = 1

            while collected < query.max_results:
                payload: dict[str, Any] = {
                    "searchWord": keyword,
                    "noticeType": "1000",
                    "pageNow": page,
                    "pageSize": min(page_size, query.max_results - collected),
                }
                if query.date_from:
                    payload["startTime"] = query.date_from.strftime("%Y:%m:%d")
                if query.date_to:
                    payload["endTime"] = query.date_to.strftime("%Y:%m:%d")

                resp = await self._post(_SEARCH_URL, json=payload)
                data = resp.json()

                items: list[dict[str, Any]] = data.get("data", {}).get("list", [])
                if not items:
                    break

                for item in items:
                    notice_id = str(item.get("id", item.get("projectCode", "")))
                    yield RawDocument(
                        source=self.source,
                        doc_type=self.doc_type,
                        raw_id=notice_id,
                        title=item.get("title"),
                        raw_data=item,
                        url=f"{_DETAIL_URL}?id={notice_id}",
                    )
                    collected += 1
                    if collected >= query.max_results:
                        return

                total = int(data.get("data", {}).get("total", 0))
                if collected >= total or len(items) < page_size:
                    break
                page += 1

        logger.info("ccgp_collect_done", keywords=query.keywords, count=collected)

    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        resp = await self._post(_DETAIL_URL, json={"id": raw_id})
        data = resp.json().get("data")
        if not data:
            return None
        return RawDocument(
            source=self.source,
            doc_type=self.doc_type,
            raw_id=raw_id,
            title=data.get("title"),
            raw_data=data,
            url=f"{_DETAIL_URL}?id={raw_id}",
        )
