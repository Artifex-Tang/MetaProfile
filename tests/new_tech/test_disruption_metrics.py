"""Phase C 纯函数:组合新颖性(Wang 无引文版)/小团队/新词比/z 归一/加权合分。"""
from __future__ import annotations

import pytest

from metaprofile.new_tech_discovery.services.disruption_metrics import (
    disrupt_score,
    new_term_ratio,
    novelty_ratio,
    pair_first_seen,
    small_team_ratio,
    z_scores,
)


def test_pair_first_seen():
    seq = {2023: {("A", "B"), ("B", "C")}, 2024: {("A", "B"), ("C", "D")}}
    fs = pair_first_seen(seq)
    assert fs == {("A", "B"): 2023, ("B", "C"): 2023, ("C", "D"): 2024}


def test_novelty_ratio_never_seen_pairs():
    patents = [{("A", "B")}, {("B", "C")}, {("A", "B")}]
    seen = {("A", "B")}  # 只有 AB 是旧对
    # 专利1 无新对; 专利2 有新对 BC; 专利3 无 → 1/3
    assert novelty_ratio(patents, seen) == pytest.approx(1 / 3)
    assert novelty_ratio([], set()) == 0.0


def test_small_team_ratio():
    assert small_team_ratio([1, 2, 1, 3], max_applicants=1) == pytest.approx(2 / 4)
    assert small_team_ratio([]) == 0.0


def test_new_term_ratio():
    hist = {"old", "quantum"}
    cur = {"quantum", "neuro"}            # neuro 新
    assert new_term_ratio(cur, hist) == pytest.approx(1 / 2)
    assert new_term_ratio(set(), hist) == 0.0


def test_z_scores_zero_variance_guard():
    z = z_scores({"a": 1.0, "b": 1.0})    # 全等 → σ=0 → 全 0
    assert z == {"a": 0.0, "b": 0.0}
    z2 = z_scores({"a": 0.0, "b": 1.0, "c": 2.0})
    assert z2["b"] == pytest.approx(0.0)  # 均值处 → 0
    assert z2["c"] > 0 and z2["a"] < 0


def test_disrupt_score_weighted_sum():
    comps = {"novelty_comb": 1.0, "growth": 1.0, "new_entrant": 1.0,
             "small_team": 1.0, "term_novelty": 1.0}
    w = (0.30, 0.25, 0.20, 0.15, 0.10)
    assert disrupt_score(comps, w) == pytest.approx(1.0)
    comps2 = {k: 0.0 for k in comps}
    assert disrupt_score(comps2, w) == 0.0
