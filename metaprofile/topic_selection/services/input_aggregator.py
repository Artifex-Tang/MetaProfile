"""输入聚合器：汇总前沿技术清单 + 弱信号 + 政策关键词，供五策略共用。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class AggregatedInput:
    frontier_techs: list[dict] = field(default_factory=list)   # scan_monitor frontier-tech list
    weak_signals: list[dict] = field(default_factory=list)      # new_tech_discovery signals
    policy_keywords: list[str] = field(default_factory=list)    # 政策关键词（来自 profile_project）
    period_from: date | None = None
    period_to: date | None = None


class InputAggregator:
    """多源输入聚合器。"""

    def __init__(self) -> None:
        self._scan_base = settings.profile_api.tech_base_url   # scan_monitor 同机部署，用同 base
        self._proj_base = settings.profile_api.project_base_url
        self._timeout = settings.profile_api.timeout_seconds

    async def aggregate(
        self,
        *,
        period_from: date,
        period_to: date,
        domain: str | None = None,
    ) -> AggregatedInput:
        frontier = await self._fetch_frontier_techs(period_from, period_to)
        keywords = await self._fetch_policy_keywords(domain)
        return AggregatedInput(
            frontier_techs=frontier,
            policy_keywords=keywords,
            period_from=period_from,
            period_to=period_to,
        )

    async def _fetch_frontier_techs(self, period_from: date, period_to: date) -> list[dict]:
        """调用 scan_monitor /frontier-tech/list 获取本期前沿技术。"""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._scan_base}{settings.api_prefix}/scan/frontier-tech/list",
                    params={
                        "period_from": period_from.isoformat(),
                        "period_to": period_to.isoformat(),
                        "page_size": 100,
                    },
                )
                if resp.status_code != 200:
                    return []
                return resp.json().get("items", [])
        except Exception as exc:
            logger.warning("input_aggregator_frontier_failed", error=str(exc))
            return []

    async def _fetch_policy_keywords(self, domain: str | None) -> list[str]:
        """从 profile_project 搜索近期政府主导项目，提取关键词。"""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                body: dict = {"page_size": 20}
                if domain:
                    body["project_domain"] = [domain]
                resp = await client.post(
                    f"{self._proj_base}{settings.api_prefix}/profile/project/search",
                    json=body,
                )
                if resp.status_code != 200:
                    return []
                items = resp.json().get("items", [])
                kws: list[str] = []
                for item in items:
                    name = item.get("name_cn") or ""
                    if isinstance(name, list):
                        kws.extend(name)
                    elif name:
                        kws.append(name)
                return list(dict.fromkeys(kws))[:50]
        except Exception as exc:
            logger.warning("input_aggregator_policy_failed", error=str(exc))
            return []
