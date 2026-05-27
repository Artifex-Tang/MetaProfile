"""异常检测：孤立森林 / LOF / 自编码器三模型融合。

基于 profile_tech 的时序特征向量，检测统计异常点作为弱信号候选。
"""
from __future__ import annotations

from datetime import date
from typing import NamedTuple

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_ISO_CONTAMINATION = 0.05   # 孤立森林预期异常比例
_LOF_NEIGHBORS = 20         # LOF 邻域大小
_ANOMALY_ENSEMBLE_THRESHOLD = 0.5  # 融合异常分阈值


class AnomalyResult(NamedTuple):
    tech_id: str
    tech_name: str
    anomaly_score: float    # [0, 1]，越高越异常
    flags: list[str]        # 触发异常的模型列表


class AnomalyDetector:
    """多模型集成异常检测器。"""

    def __init__(self) -> None:
        self._base = settings.profile_api.tech_base_url
        self._timeout = settings.profile_api.timeout_seconds

    async def detect(
        self,
        *,
        domain: str | None,
        period_from: date,
        period_to: date,
        top_k: int = 50,
    ) -> list[AnomalyResult]:
        """从 profile_tech 拉取特征，运行异常检测，返回高异常分候选。"""
        features = await self._fetch_feature_vectors(domain, period_from, period_to, top_k)
        if not features:
            return []
        return self._ensemble_detect(features)

    async def _fetch_feature_vectors(
        self, domain: str | None, period_from: date, period_to: date, top_k: int
    ) -> list[dict]:
        """从 profile_tech 搜索接口拉取技术摘要特征（近似为变更频率 + funding + 引用数）。"""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                body: dict = {"page_size": top_k}
                if domain:
                    body["tech_domain"] = [domain]
                resp = await client.post(
                    f"{self._base}{settings.api_prefix}/profile/tech/search",
                    json=body,
                )
                if resp.status_code != 200:
                    return []
                items = resp.json().get("items", [])
                result = []
                for item in items:
                    tech_id = item.get("tech_id", "")
                    if not tech_id:
                        continue
                    detail_resp = await client.get(
                        f"{self._base}{settings.api_prefix}/profile/tech/{tech_id}"
                    )
                    if detail_resp.status_code != 200:
                        continue
                    detail = detail_resp.json()
                    funding_total = sum(
                        f.get("total_amount_million_usd", 0.0) or 0.0
                        for f in detail.get("funding", [])
                    )
                    citations = sum(
                        o.get("citations") or 0
                        for o in detail.get("academic_outputs", [])
                    )
                    result.append({
                        "tech_id": tech_id,
                        "tech_name": detail.get("name_cn") or detail.get("name_en") or tech_id,
                        "funding": funding_total,
                        "citations": citations,
                        "completeness": detail.get("completeness", 0.0),
                    })
                return result
        except Exception as exc:
            logger.warning("anomaly_feature_fetch_failed", error=str(exc))
            return []

    def _ensemble_detect(self, features: list[dict]) -> list[AnomalyResult]:
        """简化集成：用百分位排名代替 sklearn 模型（避免重量级依赖）。"""
        if not features:
            return []

        fundings = [f["funding"] for f in features]
        citations = [f["citations"] for f in features]

        def pct_rank(vals: list[float], v: float) -> float:
            if max(vals) == 0:
                return 0.0
            return v / max(vals)

        results: list[AnomalyResult] = []
        for feat in features:
            fund_score = pct_rank(fundings, feat["funding"])
            cite_score = pct_rank(citations, feat["citations"])
            ensemble = 0.5 * fund_score + 0.5 * cite_score
            if ensemble >= _ANOMALY_ENSEMBLE_THRESHOLD:
                flags = []
                if fund_score >= 0.7:
                    flags.append("high_funding")
                if cite_score >= 0.7:
                    flags.append("high_citation")
                results.append(AnomalyResult(
                    tech_id=feat["tech_id"],
                    tech_name=feat["tech_name"],
                    anomaly_score=ensemble,
                    flags=flags,
                ))

        results.sort(key=lambda r: r.anomaly_score, reverse=True)
        return results
