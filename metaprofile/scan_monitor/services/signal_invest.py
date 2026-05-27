"""信号D：投融资热度信号。

通过 profile_tech 画像中的 funding 字段统计近期投融资总量，
计算相对于基线的热度异动强度。
"""
from __future__ import annotations

from datetime import date

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_INVEST_HIGH_THRESHOLD_M = 100.0  # 高投入阈值（百万美元）


class InvestSignalScorer:
    """投融资热度信号采集器。"""

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
        """返回 [0,1] 投融资热度分。"""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                body: dict = {"page_size": 5}
                if domain:
                    body["tech_domain"] = [domain]
                resp = await client.post(
                    f"{self._base}{settings.api_prefix}/profile/tech/search",
                    json=body,
                )
                if resp.status_code != 200:
                    return 0.0
                items = resp.json().get("items", [])
                if not items:
                    return 0.0
                tech_id = items[0].get("tech_id", "")
                if not tech_id:
                    return 0.0
                detail_resp = await client.get(
                    f"{self._base}{settings.api_prefix}/profile/tech/{tech_id}"
                )
                if detail_resp.status_code != 200:
                    return 0.0
                detail = detail_resp.json()
                fundings = detail.get("funding", [])
                total_invest = sum(f.get("total_amount_million_usd", 0.0) or 0.0 for f in fundings)
                return min(total_invest / _INVEST_HIGH_THRESHOLD_M, 1.0)
        except Exception as exc:
            logger.warning("invest_signal_score_failed", error=str(exc))
            return 0.0
