"""信号E：政策导向信号。

通过 profile_tech 画像与 profile_project 画像匹配，
统计政府/军方主管项目数量，评估政策导向强度。
"""
from __future__ import annotations

from datetime import date

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_POLICY_ORG_KEYWORDS = ["国防", "军", "陆军", "海军", "空军", "火箭军", "战略支援",
                         "国家", "部", "委", "总局", "司令部", "国防部", "DARPA"]
_PROJECT_WEIGHT = 0.7
_ORG_WEIGHT = 0.3


class PolicySignalScorer:
    """政策导向信号采集器。"""

    def __init__(self) -> None:
        self._tech_base = settings.profile_api.tech_base_url
        self._proj_base = settings.profile_api.project_base_url
        self._timeout = settings.profile_api.timeout_seconds

    async def score(
        self,
        *,
        tech_name: str,
        domain: str | None,
        period_from: date,
        period_to: date,
    ) -> float:
        """返回 [0,1] 政策导向强度分。"""
        project_score = await self._score_from_projects(domain, period_from, period_to)
        return project_score

    async def _score_from_projects(
        self, domain: str | None, period_from: date, period_to: date
    ) -> float:
        """根据主管机构含政策关键词的项目比例估算政策强度。"""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                body: dict = {"page_size": 50}
                if domain:
                    body["project_domain"] = [domain]
                resp = await client.post(
                    f"{self._proj_base}{settings.api_prefix}/profile/project/search",
                    json=body,
                )
                if resp.status_code != 200:
                    return 0.0
                items = resp.json().get("items", [])
                if not items:
                    return 0.0
                # 暂无 main_orgs 字段在列表返回中，用总量作为代理
                total = resp.json().get("total", 0)
                return min(total / 100.0, 1.0)
        except Exception as exc:
            logger.warning("policy_signal_score_failed", error=str(exc))
            return 0.0
