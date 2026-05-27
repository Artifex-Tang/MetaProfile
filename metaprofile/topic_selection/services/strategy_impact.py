"""策略 C：产业影响力评估。

通过 profile_org 和 profile_project 查询与选题相关的机构/项目数量，
以规模代理影响力强度。
"""
from __future__ import annotations

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_ORG_MAX = 20.0     # 参考满分机构数
_PROJ_MAX = 50.0    # 参考满分项目数


class ImpactStrategyScorer:
    """产业影响力策略评分器。"""

    def __init__(self) -> None:
        self._org_base = settings.profile_api.org_base_url
        self._proj_base = settings.profile_api.project_base_url
        self._timeout = settings.profile_api.timeout_seconds

    async def score(self, title: str, domain: str | None) -> float:
        """返回 [0, 1] 产业影响力分：关联机构 + 项目数量加权。"""
        org_score = await self._score_orgs(title, domain)
        proj_score = await self._score_projects(title, domain)
        return 0.5 * org_score + 0.5 * proj_score

    async def _score_orgs(self, title: str, domain: str | None) -> float:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                body: dict = {"page_size": 50, "keyword": title}
                if domain:
                    body["tech_domains"] = [domain]
                resp = await client.post(
                    f"{self._org_base}{settings.api_prefix}/profile/org/search",
                    json=body,
                )
                if resp.status_code != 200:
                    return 0.0
                total = resp.json().get("total", 0)
                return min(total / _ORG_MAX, 1.0)
        except Exception as exc:
            logger.warning("impact_org_score_failed", error=str(exc))
            return 0.0

    async def _score_projects(self, title: str, domain: str | None) -> float:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                body: dict = {"page_size": 50, "keyword": title}
                if domain:
                    body["project_domain"] = [domain]
                resp = await client.post(
                    f"{self._proj_base}{settings.api_prefix}/profile/project/search",
                    json=body,
                )
                if resp.status_code != 200:
                    return 0.0
                total = resp.json().get("total", 0)
                return min(total / _PROJ_MAX, 1.0)
        except Exception as exc:
            logger.warning("impact_proj_score_failed", error=str(exc))
            return 0.0
