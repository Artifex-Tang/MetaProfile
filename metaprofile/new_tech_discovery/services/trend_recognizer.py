"""趋势识别：时间序列分解 + Mann-Kendall 趋势检验。

从 profile_tech 变更记录中提取时序特征，判断技术是否处于上升趋势。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_MK_TREND_THRESHOLD = 0.6   # Mann-Kendall 归一化得分阈值（视为上升趋势）


class TrendResult(NamedTuple):
    tech_name: str
    domain: str | None
    mk_score: float       # [0, 1] 趋势强度
    is_rising: bool
    slope: float          # 线性斜率（近似）


class TrendRecognizer:
    """技术趋势识别器。"""

    def __init__(self) -> None:
        self._base = settings.profile_api.tech_base_url
        self._timeout = settings.profile_api.timeout_seconds

    async def recognize(
        self,
        *,
        domain: str | None,
        period_from: date,
        period_to: date,
        window_days: int = 7,
    ) -> list[TrendResult]:
        """按滑动窗口统计 profile_tech 变更量，运行 Mann-Kendall 检验。"""
        series = await self._build_time_series(domain, period_from, period_to, window_days)
        if len(series) < 4:
            return []
        mk_score, slope = self._mann_kendall(series)
        is_rising = mk_score >= _MK_TREND_THRESHOLD
        return [TrendResult(
            tech_name=domain or "all",
            domain=domain,
            mk_score=mk_score,
            is_rising=is_rising,
            slope=slope,
        )]

    async def _build_time_series(
        self,
        domain: str | None,
        period_from: date,
        period_to: date,
        window_days: int,
    ) -> list[float]:
        """将监测期切分为等宽窗口，每个窗口查询 profile_tech 变更量。"""
        series: list[float] = []
        cursor = period_from
        total_days = (period_to - period_from).days
        if total_days <= 0:
            return []
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                while cursor < period_to:
                    window_end = min(cursor + timedelta(days=window_days), period_to)
                    params: dict = {
                        "since": cursor.isoformat(),
                        "until": window_end.isoformat(),
                        "limit": 500,
                    }
                    if domain:
                        params["domain"] = domain
                    resp = await client.get(
                        f"{self._base}{settings.api_prefix}/profile/tech/changes",
                        params=params,
                    )
                    count = resp.json().get("total", 0) if resp.status_code == 200 else 0
                    series.append(float(count))
                    cursor = window_end
        except Exception as exc:
            logger.warning("trend_series_fetch_failed", error=str(exc))
        return series

    @staticmethod
    def _mann_kendall(series: list[float]) -> tuple[float, float]:
        """简化 Mann-Kendall：计算一致性对数 S，归一化到 [0,1]。"""
        n = len(series)
        s = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                diff = series[j] - series[i]
                if diff > 0:
                    s += 1
                elif diff < 0:
                    s -= 1
        max_s = n * (n - 1) / 2
        normalized = (s + max_s) / (2 * max_s) if max_s > 0 else 0.5

        # 线性斜率（Theil-Sen 中位数斜率近似为均值差/时间差）
        slopes = [
            (series[j] - series[i]) / (j - i)
            for i in range(n - 1)
            for j in range(i + 1, n)
        ]
        slope = sorted(slopes)[len(slopes) // 2] if slopes else 0.0
        return normalized, slope
