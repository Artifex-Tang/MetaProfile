"""Phase B 新兴指标层纯函数测试(B1 Porter / B2 TLC / B3 TEM / B4 IPC 共类)。

公式出处见 spec 2026-10-14 §2.1(方法调研 2026-10-14)。
"""
from __future__ import annotations

import math

import pytest

from metaprofile.new_tech_discovery.services.emergence_metrics import (
    doubling_time,
    haupt_ratio,
    porter_indicators,
    s_curve_stage,
    salton,
    tem_quadrants,
)

# ── B1 Porter ──

def test_porter_active_and_new_entrant_ratio():
    windows = [{"A", "B"}, {"B", "C"}, {"C", "D", "E"}]
    out = porter_indicators(windows)
    assert [x["active_entities"] for x in out] == [2, 2, 3]
    assert out[0]["new_entrant_ratio"] == 1.0          # 首窗全是新进入者
    assert out[1]["new_entrant_ratio"] == pytest.approx(0.5)      # C 新,B 旧
    assert out[2]["new_entrant_ratio"] == pytest.approx(2 / 3)    # D,E 新


def test_doubling_time_formula():
    # g=0.5 → DT = ln2/ln1.5 ≈ 1.7095
    assert doubling_time(10, 15) == pytest.approx(math.log(2) / math.log(1.5))
    assert doubling_time(10, 10) is None   # 零增长
    assert doubling_time(10, 5) is None    # 负增长
    assert doubling_time(0, 5) is None     # 无基线


# ── B2 TLC ──

def test_haupt_ratio():
    # 专利 CAGR=1.0(10→40 over 2 步),申请人 CAGR=0.5(5→13≈x2.6→0.6?) 用精确数
    ratio = haupt_ratio(patents=[10, 20, 40], applicants=[10, 20, 30])
    pg = (40 / 10) ** 0.5 - 1     # 1.0
    ag = (30 / 10) ** 0.5 - 1     # ≈0.732
    assert ratio == pytest.approx(pg / ag)
    assert haupt_ratio([10, 10], [5, 5]) is None  # 申请人零增长


def test_s_curve_stage_early_is_emerging():
    # 合成 logistic: L=100,k=0.8,t0=15,取 t=0..9 → 早期
    import numpy as np  # noqa: F401 (服务端有,公式用纯 python 重算也行)
    ts = list(range(10))
    L, k, t0 = 100.0, 0.8, 15.0
    cum = [L / (1 + math.exp(-k * (t - t0))) for t in ts]
    assert s_curve_stage(ts, cum) in ("emerging", "growth")


def test_s_curve_stage_late_is_mature_or_saturated():
    ts = list(range(0, 40, 2))
    L, k, t0 = 100.0, 0.6, 12.0
    cum = [L / (1 + math.exp(-k * (t - t0))) for t in ts]
    assert s_curve_stage(ts, cum) in ("mature", "saturated")


def test_s_curve_stage_insufficient_data():
    assert s_curve_stage([0, 1], [1.0, 2.0]) == "insufficient"


# ── B3 TEM 象限 ──

def test_tem_quadrants_classification():
    # 切点 x=均值份额, y=0
    shares = {"a": 0.1, "b": 0.5}          # mean = 0.3
    growths = {"a": 0.4, "b": -0.1}
    q = tem_quadrants(shares, growths)
    assert q["a"] == "weak"      # 低份额高增
    assert q["b"] == "nswb"      # 高份额负增
    q2 = tem_quadrants({"a": 0.6, "b": 0.05}, {"a": 0.2, "b": -0.3})
    assert q2["a"] == "strong"   # 高份额高增
    assert q2["b"] == "latent"   # 低份额低增


# ── B4 IPC 共类(Salton)──

def test_salton_formula():
    assert salton(2, 4, 9) == pytest.approx(2 / 6)
    assert salton(0, 4, 9) == 0.0


def test_emerging_pairs_new_and_rising():
    from metaprofile.new_tech_discovery.services.emergence_metrics import (
        emerging_pairs,
    )
    # 域计数:G06T 4 篇, G06N 9 篇; 对 (G06T,G06N) 2023 首现 1, 2024 升 2 → 新且升
    pairs = {
        2023: {("G06N", "G06T"): 1},
        2024: {("G06N", "G06T"): 2},
    }
    domain_counts = {
        2023: {"G06T": 3, "G06N": 8},
        2024: {"G06T": 4, "G06N": 9},
    }
    out = emerging_pairs(pairs, domain_counts, lookback_years=3, min_salton=0.05)
    assert len(out) == 1
    p = out[0]
    assert p["object_id"] == "G06N|G06T"
    assert p["first_seen"] == 2023
    assert p["is_new_pair"] is True
    assert p["salton_rising"] is True
    assert p["salton"] == pytest.approx(2 / 6)
