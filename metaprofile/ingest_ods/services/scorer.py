"""阶段④ 数据质量评分（规则型，零 LLM，ISO 25012 对齐）。

返回 dict：completeness / veracity_score / timeliness_score / data_as_of / dq_index。
接口 score(profile_type, attrs, source_rows) 与原 LLM Scorer 一致 → orchestrator 零改。
"""
from __future__ import annotations

from datetime import date

import structlog

from metaprofile.foundation.enrichment.completeness import score_completeness
from metaprofile.ingest_ods.services.quality_rules import (
    credibility_score, timeliness_score,
)
from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import EntityType

logger = structlog.get_logger(__name__)

# profile_type 字符串 → EntityType 枚举（score_completeness 需要）
_PT2ET = {
    "tech": EntityType.TECH, "org": EntityType.ORG,
    "person": EntityType.PERSON, "project": EntityType.PROJECT,
}


def _latest_as_of(source_rows: list[dict]) -> date | None:
    """取 source_rows 中最新 update_time/event_time 为 data_as_of。"""
    best: date | None = None
    for r in source_rows:
        rp = r.get("raw_payload", {}) if isinstance(r, dict) else {}
        for k in ("update_time", "event_time"):
            v = rp.get(k)
            if not v:
                continue
            try:
                d = date.fromisoformat(str(v)[:10])
            except Exception:
                continue
            if d > date.today():  # I4: 跳过未来日期，避免污染 freshness
                continue
            if best is None or d > best:
                best = d
    return best


class RuleScorer:
    """确定性规则评分器（无 LLM 依赖）。"""

    def __init__(self, llm=None) -> None:  # llm 保留仅为接口兼容(legacy 调用)，不使用
        pass

    async def score(self, profile_type: str, attrs: dict,
                    source_rows: list[dict]) -> dict:
        t = settings.thresholds
        et = _PT2ET.get(profile_type)
        completeness = score_completeness(et, attrs).score if et is not None else 0.0
        data_as_of = _latest_as_of(source_rows)
        veracity = credibility_score(source_rows[0] if source_rows else {}, attrs, profile_type)
        timeliness = timeliness_score(data_as_of)
        dq = (t.dq_weight_completeness * completeness
              + t.dq_weight_veracity * veracity
              + t.dq_weight_timeliness * timeliness)
        return {
            "completeness": round(completeness, 4),
            "veracity_score": round(veracity, 4),
            "timeliness_score": round(timeliness, 4),
            "data_as_of": data_as_of,
            "dq_index": round(dq, 4),
        }

