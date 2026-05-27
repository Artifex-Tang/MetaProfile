"""
关键词突现检测（简化 Kleinberg 模型）。

基于滑动窗口近似，判断某关键词在时序文档流中是否处于突现状态。
适用于：前沿技术扫描、新技术发现的早期信号识别。
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass


@dataclass
class BurstResult:
    keyword: str
    burst_score: float
    recent_freq: float
    baseline_freq: float
    is_bursting: bool


def compute_burst_scores(
    time_series: list[dict[str, int]],
    *,
    recent_window: int = 3,
    burst_threshold: float = 2.0,
    min_total_count: int = 3,
) -> list[BurstResult]:
    """
    计算关键词突现分数。

    Args:
        time_series: 时序频率数据，每个元素是 {keyword: count} 字典，
                     按时间从旧到新排列（每个元素代表一个时间片，如一周）。
        recent_window: 近期窗口大小（时间片数），用于计算近期频率。
        burst_threshold: 近期频率/基线频率 >= 此值视为突现。
        min_total_count: 总出现次数低于此值的词过滤掉（避免低频噪声）。

    Returns:
        按 burst_score 降序排列的突现分析结果。
    """
    if not time_series:
        return []

    total_counts: Counter[str] = Counter()
    for slot in time_series:
        for kw, cnt in slot.items():
            total_counts[kw] += cnt

    recent_slots = time_series[-recent_window:]
    recent_counts: Counter[str] = Counter()
    for slot in recent_slots:
        for kw, cnt in slot.items():
            recent_counts[kw] += cnt

    n_total = len(time_series)
    n_recent = len(recent_slots)

    results: list[BurstResult] = []
    for kw, total_cnt in total_counts.items():
        if total_cnt < min_total_count:
            continue
        baseline_freq = total_cnt / n_total
        recent_freq = recent_counts.get(kw, 0) / n_recent if n_recent > 0 else 0.0

        if baseline_freq == 0:
            burst_score = 0.0
            is_bursting = False
        else:
            ratio = recent_freq / baseline_freq
            burst_score = math.log1p(ratio) if ratio > 1 else 0.0
            is_bursting = ratio >= burst_threshold

        results.append(
            BurstResult(
                keyword=kw,
                burst_score=burst_score,
                recent_freq=recent_freq,
                baseline_freq=baseline_freq,
                is_bursting=is_bursting,
            )
        )

    results.sort(key=lambda r: r.burst_score, reverse=True)
    return results
