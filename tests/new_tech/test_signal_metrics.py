from metaprofile.new_tech_discovery.services.signal_metrics import (
    burst_score,
    coherence_score,
    diversity_score,
    mann_kendall_tau,
    novelty_score,
    velocity_score,
)


def test_burst_score_zero_when_at_baseline():
    # df_current == mean(history) → 0
    assert burst_score(5, [5, 5, 5]) == 0.0


def test_burst_score_positive_above_baseline():
    # history [3,7]: mean=5, pstdev=2 → (9-5)/2 = 2.0
    assert abs(burst_score(9, [3, 7]) - 2.0) < 1e-6


def test_burst_score_clamped_nonnegative():
    # df_current below baseline → max(0, negative) = 0
    assert burst_score(1, [5, 5, 5]) == 0.0


def test_burst_score_no_history_returns_zero():
    assert burst_score(10, []) == 0.0


def test_novelty_brand_new_term():
    # 从未在历史窗出现 → 1.0
    assert novelty_score(history_windows_seen=0, total_history_windows=6) == 1.0


def test_novelty_long_existing():
    # 全部历史窗都出现 → 趋近 0
    assert novelty_score(history_windows_seen=6, total_history_windows=6) == 0.0


def test_novelty_half_seen():
    assert abs(novelty_score(3, 6) - 0.5) < 1e-6


def test_novelty_no_history_is_fully_new():
    # 无历史窗 → 视为全新
    assert novelty_score(0, 0) == 1.0


def test_diversity_single_source_is_zero():
    assert diversity_score({"science": 10}) == 0.0


def test_diversity_uniform_four_sources_is_one():
    # 均匀 4 源 → 归一化熵 = 1.0
    result = diversity_score({"science": 1, "patent": 1, "market": 1, "attachment": 1})
    assert abs(result - 1.0) < 1e-6


def test_diversity_two_sources_midpoint():
    # 均匀 2 源 → 归一化熵 = log(2)/log(2) = 1.0
    # （注：原 plan 注释 log(4) 为误，n=2 时除以 log(2)）
    assert abs(diversity_score({"science": 1, "patent": 1}) - 1.0) < 1e-3


def test_diversity_empty_is_zero():
    assert diversity_score({}) == 0.0


def test_coherence_all_sources_rising():
    cur = {"science": 5, "patent": 6, "market": 4}
    prev = {"science": 2, "patent": 1, "market": 1}
    assert coherence_score(cur, prev) == 1.0


def test_coherence_none_rising():
    cur = {"science": 1, "patent": 1}
    prev = {"science": 5, "patent": 5}
    assert coherence_score(cur, prev) == 0.0


def test_coherence_no_previous_is_zero():
    # 无上一窗基线 → 无法判断一致性 → 0
    assert coherence_score({"science": 5}, {}) == 0.0


def test_coherence_partial():
    cur = {"science": 5, "patent": 1, "market": 5}
    prev = {"science": 1, "patent": 5, "market": 1}
    # science/market 升、patent 降 → 2/3
    assert abs(coherence_score(cur, prev) - (2 / 3)) < 1e-6


def test_mk_tau_rising():
    assert mann_kendall_tau([1, 2, 3, 4, 5]) == 1.0


def test_mk_tau_falling():
    assert mann_kendall_tau([5, 4, 3, 2, 1]) == -1.0


def test_mk_tau_flat():
    assert abs(mann_kendall_tau([3, 3, 3, 3]) - 0.0) < 1e-6


def test_mk_tau_too_short():
    assert mann_kendall_tau([1]) == 0.0
    assert mann_kendall_tau([]) == 0.0


def test_velocity_score_rising_significant():
    # 显著上升序列 → 归一化斜率明显高于平坦(0);[2,4,8] slope=3/ymax8=0.375
    v = velocity_score([2, 4, 8])
    assert v > 0.3


def test_velocity_score_flat_is_zero():
    assert velocity_score([3, 3, 3]) == 0.0


def test_velocity_score_halved_when_trend_insignificant():
    # 同样上升曲线，但显式传 tau < threshold → 折半
    full = velocity_score([2, 4, 8])
    halved = velocity_score([2, 4, 8], tau=0.0, tau_threshold=0.6)
    assert abs(halved - full / 2) < 1e-6


def test_velocity_score_clamped_to_one():
    assert velocity_score([0, 0, 100]) <= 1.0


from datetime import date  # noqa: E402

from metaprofile.new_tech_discovery.services.signal_metrics import (  # noqa: E402
    build_term_stats,
    build_windows,
    tokenize,
)


def test_tokenize_chinese_jieba():
    toks = tokenize("量子计算与机器学习", lang="zh")
    assert "量子" in toks or "量子计算" in toks
    assert "的" not in toks  # 停用词过滤


def test_tokenize_english_lowercased():
    toks = tokenize("Quantum Computing is GREAT", lang="en")
    assert "quantum" in toks and "computing" in toks
    assert "is" not in toks  # 停用词


def test_build_windows_monthly():
    ws = build_windows(period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
                       lookback_months=2, window_months=1)
    # 2 历史(2025-11,2025-12) + 3 当前(2026-01,02,03) = 5 窗
    assert len(ws) == 5
    assert ws[0].is_history is True
    assert ws[-1].is_history is False
    assert all(w.end >= w.start for w in ws)


def test_build_term_stats_collects_df_series():
    from metaprofile.new_tech_discovery.services.corpus_loader import CorpusDoc
    docs = [
        CorpusDoc("science", "1", "quantum qubit", date(2026, 1, 10), []),
        CorpusDoc("patent", "2", "quantum chip", date(2026, 2, 10), ["ACME"]),
    ]
    windows = build_windows(date(2026, 1, 1), date(2026, 2, 28), lookback_months=0, window_months=1)
    stats = build_term_stats(docs, windows, min_df=1)
    # "quantum" 出现于 2 窗（1 月、2 月）
    q = next(s for s in stats if s.term == "quantum")
    assert sum(q.df_by_window) == 2
    assert "science" in q.df_by_source or "ods_science_literature" in q.df_by_source
