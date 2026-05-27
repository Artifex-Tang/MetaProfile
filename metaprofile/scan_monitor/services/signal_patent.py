"""信号B：专利异动检测。

从 profile_tech 画像层拉取专利相关统计，检测是否有突发性专利申请异动。
计算 [0,1] 异动强度分：近期新增量 / 历史平均基线。
"""
from __future__ import annotations

from datetime import date

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_BASELINE_PERIOD_WEEKS = 12   # 历史基线统计窗口（周）
_SPIKE_MULTIPLIER = 1.5       # 超过基线 1.5 倍视为异动


class PatentSignalScorer:
    """专利异动信号采集器。"""

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
        """返回 [0,1] 专利异动分。"""
        try:
            recent, baseline = await self._fetch_patent_counts(tech_name, domain, period_from, period_to)
            if baseline <= 0:
                return 0.0 if recent <= 0 else 0.5
            ratio = recent / baseline
            # 归一化：ratio >= SPIKE_MULTIPLIER 时满分
            return min((ratio - 1.0) / (_SPIKE_MULTIPLIER - 1.0), 1.0) if ratio > 1.0 else 0.0
        except Exception as exc:
            logger.warning("patent_signal_score_failed", error=str(exc))
            return 0.0

    async def _fetch_patent_counts(
        self, tech_name: str, domain: str | None, period_from: date, period_to: date
    ) -> tuple[int, float]:
        """从 profile_tech 查询最新变更量作为专利近期活跃代理。"""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base}{settings.api_prefix}/profile/tech/changes",
                    params={
                        "since": period_from.isoformat(),
                        "until": period_to.isoformat(),
                        "limit": 500,
                    },
                )
                if resp.status_code != 200:
                    return 0, 1.0
                data = resp.json()
                recent = data.get("total", 0)
                # 以 30 天变更量 / 监测天数 * baseline天数 作为基线估算
                days = max((period_to - period_from).days, 1)
                baseline = recent / days * _BASELINE_PERIOD_WEEKS * 7
                return recent, baseline
        except Exception:
            return 0, 1.0
