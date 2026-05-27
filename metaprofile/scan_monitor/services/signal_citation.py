"""信号C：引用聚类信号。

通过 profile_tech 画像中的 academic_outputs 统计引用密集度，
检测是否出现高引聚集（新兴核心论文簇）。
"""
from __future__ import annotations

from datetime import date

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_HIGH_CITATION_THRESHOLD = 50  # 高引论文阈值（引用次数）
_MIN_CLUSTER_SIZE = 3          # 最小簇规模


class CitationSignalScorer:
    """引用聚类信号采集器。"""

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
        """返回 [0,1] 引用聚类强度分。"""
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
                outputs = detail.get("academic_outputs", [])
                high_cited = [o for o in outputs if (o.get("citations") or 0) >= _HIGH_CITATION_THRESHOLD]
                cluster_score = min(len(high_cited) / _MIN_CLUSTER_SIZE, 1.0)
                return cluster_score
        except Exception as exc:
            logger.warning("citation_signal_score_failed", error=str(exc))
            return 0.0
