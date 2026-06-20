"""弱信号维度纯函数（专利技术方案 §4 公式）。

全部纯函数、无 IO、无随机 —— 便于 TDD 与发明专利复现。
"""
from __future__ import annotations

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
