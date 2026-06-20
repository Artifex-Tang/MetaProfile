"""自适应阈值：根据历史弱信号强度分布动态调整识别截断点。

使用历史 weak_signal 表中的 strength 分布，以均值 + k*标准差作为阈值。
"""
from __future__ import annotations

from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import WeakSignalORM
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_DEFAULT_THRESHOLD = 0.40


class AdaptiveThreshold:
    """自适应阈值计算器。"""

    def __init__(self, db: AsyncSession, *, k_sigma: float | None = None) -> None:
        self._db = db
        # k_sigma 默认取 settings.weak_signal.adaptive_k_sigma（§4.8），
        # 支持显式覆盖以便测试。
        self._k_sigma = (
            settings.weak_signal.adaptive_k_sigma if k_sigma is None else k_sigma
        )

    async def compute(
        self,
        *,
        domain: str | None = None,
        lookback_days: int = 90,
        reference_date: date | None = None,
    ) -> float:
        """查询历史 weak_signal 强度分布，返回自适应阈值。"""
        try:
            q = select(
                func.avg(WeakSignalORM.strength).label("mean"),
                func.stddev_pop(WeakSignalORM.strength).label("std"),
            )
            if domain:
                q = q.where(WeakSignalORM.domain == domain)
            row = (await self._db.execute(q)).one()
            mean = float(row.mean or 0.0)
            std = float(row.std or 0.0)
            threshold = mean + self._k_sigma * std
            return max(min(threshold, 1.0), _DEFAULT_THRESHOLD)
        except Exception as exc:
            logger.warning("adaptive_threshold_compute_failed", error=str(exc))
            return _DEFAULT_THRESHOLD

    @staticmethod
    def is_above(strength: float, threshold: float) -> bool:
        return strength >= threshold
