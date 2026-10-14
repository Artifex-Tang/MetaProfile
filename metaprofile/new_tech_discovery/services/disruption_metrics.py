"""颠覆性识别纯函数(Phase C,零 LLM 部分)。

方法出处(spec 2026-10-14 §2.1):
- Wang/Veugelers/Stephan 组合新颖性(NBER w22180)无引文改造:
  文档 IPC 对中"历史从未出现"的对 → 域级新颖度 = 含新对专利占比
- 小团队占比(Wu/Wang/Evans 2019 近似):申请人 ≤ 阈值 的专利占比
- 新词比:域内专利标题 token 首现占比(弱信号 novelty 的域级聚合)
- DisruptScore = z 加权(中文漏斗模型合成,权重可配)
"""
from __future__ import annotations

import math


def pair_first_seen(pairs_by_year: dict[int, set[tuple[str, str]]]) -> dict[tuple[str, str], int]:
    """逐年对集合 → 对首现年。"""
    first: dict[tuple[str, str], int] = {}
    for y in sorted(pairs_by_year):
        for pair in pairs_by_year[y]:
            first.setdefault(pair, y)
    return first


def novelty_ratio(patent_pair_sets: list[set[tuple[str, str]]],
                  seen_pairs: set[tuple[str, str]]) -> float:
    """含 ≥1 历史未见过对的专利占比(Wang NEW_p 的域级聚合)。"""
    if not patent_pair_sets:
        return 0.0
    novel = sum(1 for pairs in patent_pair_sets if pairs - seen_pairs)
    return novel / len(patent_pair_sets)


def small_team_ratio(applicant_counts: list[int], *, max_applicants: int = 1) -> float:
    """申请人 ≤ max_applicants 的专利占比(小团队颠覆近似)。"""
    if not applicant_counts:
        return 0.0
    small = sum(1 for c in applicant_counts if c <= max_applicants)
    return small / len(applicant_counts)


def new_term_ratio(current_terms: set[str], history_terms: set[str]) -> float:
    """当前期 token 中历史未出现的占比。"""
    if not current_terms:
        return 0.0
    return len(current_terms - history_terms) / len(current_terms)


def z_scores(values: dict[str, float]) -> dict[str, float]:
    """跨对象 z 归一(σ=0 → 全 0,防单对象除零)。"""
    if not values:
        return {}
    vals = list(values.values())
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var)
    if std < 1e-12:
        return {k: 0.0 for k in values}
    return {k: (v - mean) / std for k, v in values.items()}


_DEFAULT_WEIGHTS = {
    "novelty_comb": 0.30, "growth": 0.25, "new_entrant": 0.20,
    "small_team": 0.15, "term_novelty": 0.10,
}


def disrupt_score(z_components: dict[str, float],
                  weights: dict[str, float] | tuple | list | None = None) -> float:
    """z 加权合成。weights 支持 dict 或按 _W_ORDER 序的 5 元组;缺项按 0。"""
    _W_ORDER = ("novelty_comb", "growth", "new_entrant", "small_team", "term_novelty")
    if weights is None:
        w = _DEFAULT_WEIGHTS
    elif isinstance(weights, dict):
        w = weights
    else:
        w = dict(zip(_W_ORDER, weights, strict=True))
    return sum(w.get(k, 0.0) * v for k, v in z_components.items())
