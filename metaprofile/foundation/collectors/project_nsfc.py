"""
国家自然科学基金（NSFC）项目采集适配器。

接口：基金委项目查询系统（依赖 HTML 解析，结构化字段有限）。
文档类型：project
"""
from __future__ import annotations

import re
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

_QUERY_URL = f"{settings.collectors.nsfc_base_url}/getProjectByParam.action"
_DETAIL_URL = f"{settings.collectors.nsfc_base_url}/getProjectDetail.action"


class NSFCCollector(AbstractCollector):
    source = "nsfc"
    doc_type = "project"

    async def collect(self, query: CollectQuery) -> AsyncIterator[RawDocument]:  # type: ignore[override]
        """
        NSFC 项目检索（表单提交，JSON 响应）。
        字段：pjNo（项目编号）、pjName、pi（负责人）、orgName（依托单位）。
        """
        page = 1
        page_size = 20
        collected = 0

        for keyword in query.keywords:
            if collected >= query.max_results:
                break
            while collected < query.max_results:
                payload: dict[str, Any] = {
                    "searchWord": keyword,
                    "pageNo": page,
                    "pageSize": min(page_size, query.max_results - collected),
                    "t": "0",  # 检索范围：全部
                }
                if query.date_from:
                    payload["startYear"] = str(query.date_from.year)
                if query.date_to:
                    payload["endYear"] = str(query.date_to.year)

                resp = await self._post(_QUERY_URL, data=payload)
                data = resp.json()

                items: list[dict[str, Any]] = data.get("result", {}).get("data", [])
                if not items:
                    break

                for item in items:
                    pj_no = item.get("pjNo", "")
                    yield RawDocument(
                        source=self.source,
                        doc_type=self.doc_type,
                        raw_id=pj_no,
                        title=item.get("pjName"),
                        raw_data=item,
                        url=f"{_DETAIL_URL}?pjNo={pj_no}",
                    )
                    collected += 1
                    if collected >= query.max_results:
                        return

                total = int(data.get("result", {}).get("total", 0))
                if collected >= total or len(items) < page_size:
                    break
                page += 1

        logger.info("nsfc_collect_done", keywords=query.keywords, count=collected)

    async def get_by_id(self, raw_id: str) -> RawDocument | None:
        resp = await self._post(_DETAIL_URL, data={"pjNo": raw_id})
        data = resp.json().get("result")
        if not data:
            return None
        return RawDocument(
            source=self.source,
            doc_type=self.doc_type,
            raw_id=raw_id,
            title=data.get("pjName"),
            raw_data=data,
            url=f"{_DETAIL_URL}?pjNo={raw_id}",
        )
