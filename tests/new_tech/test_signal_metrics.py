from metaprofile.new_tech_discovery.services.signal_metrics import burst_score, novelty_score


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
