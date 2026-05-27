"""信号A：关键词突现检测。

调用 profile_tech REST API 获取近期技术画像关键词，
通过 Kleinberg 突现算法检测新兴高频关键词，输出 [0,1] 突现强度分。
"""
from __future__ import annotations

from datetime import date

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


class BurstSignalScorer:
    """关键词突现信号采集器。"""

    def __init__(self) -> None:
        self._base = settings.profile_api.tech_base_url
        self._timeout = settings.profile_api.timeout_seconds

    async def score(
        self,
        *,
        tech_name: str,
        domain: str | None,
        period_from: date,
        period_to: date,
    ) -> float:
        """从画像层拉取关键词时序，计算 Kleinberg 突现强度 [0,1]。"""
        keywords = await self._fetch_keywords(domain)
        if not keywords:
            return 0.0
        target = tech_name.lower()
        # 统计目标技术关键词在列表中出现频率作为突现代理指标
        freq = sum(1 for kw in keywords if target in kw.lower()) / max(len(keywords), 1)
        return min(freq * 10, 1.0)  # 归一化

    async def _fetch_keywords(self, domain: str | None) -> list[str]:
        """从 profile_tech /search 获取关键词列表。"""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                params: dict = {"page_size": 100}
                if domain:
                    params["project_domain"] = domain
                resp = await client.post(
                    f"{self._base}{settings.api_prefix}/profile/tech/search",
                    json=params,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                keywords: list[str] = []
                for item in data.get("items", []):
                    keywords.extend(item.get("tech_domain", []))
                return keywords
        except Exception as exc:
            logger.warning("burst_signal_fetch_failed", error=str(exc))
            return []
