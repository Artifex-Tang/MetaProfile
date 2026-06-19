"""数据质量评分纯函数（规则型，ISO 25012 对齐）。零 LLM、确定性、可单测。

- timeliness: data_as_of 指数衰减（halflife 天半衰期）
- credibility(真实性=Credibility+Accuracy): 来源权重 + 权威信号 + 一致性乘子
- authority_bonus: DOI/引用/官方编号 信号加分（cap）
- consistency_factor: 跨字段一致性（日期顺序等）
"""
from __future__ import annotations

import math
from datetime import date

from metaprofile.shared.config.settings import settings

_AUTHORITY_FIELDS = ("doi", "citation", "usc_code", "orcid", "patent_no", "project_no")
_UGC_HINTS = ("web", "crawl", "ugc")


def timeliness_score(data_as_of: date | None) -> float:
    """data_as_of 的指数衰减得分；None => 0。

    用 ln2 缩放：在 halflife 天处得分恰为 0.5（真正的“半衰期”语义）。
    """
    if data_as_of is None:
        return 0.0
    age = (date.today() - data_as_of).days
    if age < 0:
        age = 0
    halflife = settings.thresholds.timeliness_halflife_days
    return max(0.0, min(1.0, math.exp(-age * math.log(2) / halflife)))


def authority_bonus(attrs: dict) -> float:
    """每个权威信号加分，封顶 authority_bonus_cap。"""
    t = settings.thresholds
    n = sum(1 for f in _AUTHORITY_FIELDS if attrs.get(f) not in (None, "", []))
    return min(t.authority_bonus_cap, n * t.authority_bonus_each)


def consistency_factor(profile_type: str, attrs: dict) -> float:
    """跨字段一致性乘子：日期倒序等违规返回 bad，否则 ok。"""
    t = settings.thresholds
    inv = attrs.get("invention_date")
    app = attrs.get("application_date")
    if (
        inv
        and app
        and isinstance(inv, date)
        and isinstance(app, date)
        and inv > app
    ):
        return t.consistency_factor_bad
    start = attrs.get("start_date")
    end = attrs.get("end_date")
    if (
        profile_type == "project"
        and start
        and end
        and isinstance(start, date)
        and isinstance(end, date)
        and start > end
    ):
        return t.consistency_factor_bad
    return t.consistency_factor_ok


def _source_trust(src: dict) -> float:
    """按来源表/渠道映射可信度基础分。"""
    t = settings.thresholds
    tbl = (src.get("source_table") or "").lower()
    if tbl.startswith("ods_"):
        return t.source_trust_ods
    if any(h in tbl for h in _UGC_HINTS):
        return t.source_trust_ugc
    ch = (src.get("source_channel") or "").lower()
    if ch in ("llm", "enrich"):
        return t.source_trust_llm
    if ch in ("import", "bulk"):
        return t.source_trust_import
    return t.source_trust_unknown


def credibility_score(src: dict, attrs: dict, profile_type: str = "tech") -> float:
    """真实性得分 = (来源分 + 权威加分) * 一致性乘子，仅在最终 clamp 到 [0,1]。

    中间 base 不 clamp：权威加分可使 ODS 基线 0.9 升至 1.05，再乘一致性 0.85 = 0.8925，
    仍落在 [0,1] 内。一致性乘子本就有意“惩罚”高分源的不一致记录。
    """
    base = _source_trust(src) + authority_bonus(attrs)
    return max(0.0, min(1.0, base * consistency_factor(profile_type, attrs)))
