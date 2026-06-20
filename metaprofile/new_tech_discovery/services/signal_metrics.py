"""弱信号维度纯函数（专利技术方案 §4 公式）。

全部纯函数、无 IO、无随机 —— 便于 TDD 与发明专利复现。
"""
from __future__ import annotations

import math
import statistics


def burst_score(df_current: int, df_history: list[int], eps: float = 1e-6) -> float:
    """突现 z-score（§4.2）：max(0, (df_current − E) / (σ + ε))。

    E=历史均值，σ=历史标准差（总体）。无历史→0（无基线不算突现）。
    """
    if not df_history:
        return 0.0
    mean = statistics.fmean(df_history)
    std = statistics.pstdev(df_history)
    return max(0.0, (df_current - mean) / (std + eps))


def novelty_score(history_windows_seen: int, total_history_windows: int) -> float:
    """新颖度（§4.3）：1 − clamp(seen / total, 0, 1)。无历史→1.0（全新）。"""
    if total_history_windows <= 0:
        return 1.0
    ratio = max(0.0, min(1.0, history_windows_seen / total_history_windows))
    return 1.0 - ratio


def diversity_score(df_by_source: dict[str, int]) -> float:
    """多源多样性（§4.4）：归一化 Shannon 熵 −Σ p·log p / log(|S|)。

    单源/空→0；均匀 N 源→1。
    """
    sources = [s for s, c in df_by_source.items() if c > 0]
    n = len(sources)
    if n <= 1:
        return 0.0
    total = sum(df_by_source[s] for s in sources)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for s in sources:
        p = df_by_source[s] / total
        entropy -= p * math.log(p)
    return entropy / math.log(n)


def coherence_score(df_by_source_current: dict[str, int],
                    df_by_source_prev: dict[str, int]) -> float:
    """一致性（§4.6）：当前窗源频次"上升"的源占比。

    无上一窗基线(prev 空)→0（无法判一致性）。
    """
    sources = list(df_by_source_current.keys())
    if not df_by_source_prev or not sources:
        return 0.0
    rising = sum(
        1 for s in sources
        if df_by_source_current.get(s, 0) > df_by_source_prev.get(s, 0)
    )
    return rising / len(sources)


def mann_kendall_tau(series: list[float]) -> float:
    """Mann-Kendall 趋势 τ（§4.5，归一化到 [−1,1]）。

    S=Σ sign(x_j−x_i)，归一化 S/(n(n−1)/2)。n<2→0。
    """
    n = len(series)
    if n < 2:
        return 0.0
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = series[j] - series[i]
            if diff > 0:
                s += 1
            elif diff < 0:
                s -= 1
    return s / (n * (n - 1) / 2)


def velocity_score(df_recent: list[int],
                   tau: float | None = None,
                   tau_threshold: float = 0.6) -> float:
    """增速（§4.5）：归一化线性回归斜率，clamp[0,1]。

    tau 未传→用 mann_kendall_tau(df_recent) 算；τ<tau_threshold（趋势不显著）→ 折半。
    斜率 = Σ(t−t̄)(y−ȳ)/Σ(t−t̄)²；归一化除以 df 最大值。
    """
    m = len(df_recent)
    if m < 2:
        return 0.0
    ymax = max(df_recent)
    if ymax <= 0:
        return 0.0
    ts = list(range(m))
    t_mean = sum(ts) / m
    y_mean = sum(df_recent) / m
    num = sum((t - t_mean) * (y - y_mean) for t, y in zip(ts, df_recent, strict=True))
    den = sum((t - t_mean) ** 2 for t in ts)
    slope = num / den if den != 0 else 0.0
    score = max(0.0, min(1.0, slope / ymax))
    if tau is None:
        tau = mann_kendall_tau([float(y) for y in df_recent])
    if tau < tau_threshold:
        score /= 2.0
    return score
