"""新兴技术指标纯函数(Phase B,零 LLM,全库统计)。

方法出处(spec 2026-10-14 §2.1):
- B1 Porter 新兴指标:活跃实体/新进入者占比/倍增时间
- B2 TLC:Haupt 增速比(专利 CAGR/申请人 CAGR)+ S 曲线阶段(Logistic/Gompertz AIC 择优)
- B3 TEM 象限(WISDOM arXiv:2409.15340):份额×增速,切点 x=全体均值,y=0
- B4 IPC 共类融合(Curran & Leker 2011):Salton 强度,新对=首现年近且强度升

全部纯函数无 IO(专利公式可复现)。
"""
from __future__ import annotations

import math
from itertools import combinations

_MIN_CURVE_POINTS = 6


# ── B1 Porter ──

def porter_indicators(window_entities: list[set[str]]) -> list[dict]:
    """每窗实体集合序列 → [{active_entities, new_entrant_ratio}]。

    新进入者 = 本窗出现但此前所有窗未出现的实体占比。
    """
    seen: set[str] = set()
    out: list[dict] = []
    for ents in window_entities:
        active = set(ents)
        new = active - seen
        out.append({
            "active_entities": len(active),
            "new_entrant_ratio": (len(new) / len(active)) if active else 0.0,
        })
        seen |= active
    return out


def doubling_time(prev: float, cur: float) -> float | None:
    """倍增时间 DT = ln2/ln(1+g),g=(cur/prev)-1。无/零/负增长 → None。"""
    if prev <= 0 or cur <= prev:
        return None
    g = cur / prev - 1
    return math.log(2) / math.log(1 + g)


def _cagr(series: list[float]) -> float | None:
    if len(series) < 2 or series[0] <= 0 or series[-1] <= 0:
        return None
    return (series[-1] / series[0]) ** (1 / (len(series) - 1)) - 1


def haupt_ratio(patents: list[float], applicants: list[float]) -> float | None:
    """Haupt 比 = 专利 CAGR / 申请人 CAGR(近年窗口)。

    >1 = 人均产出上升(growth 期特征);申请人零/负增长 → None。
    """
    pg = _cagr(patents)
    ag = _cagr(applicants)
    if pg is None or ag is None or ag <= 0:
        return None
    return pg / ag


# ── B2 S 曲线阶段 ──

def _logistic(t, L, k, t0):
    import numpy as np
    return L / (1 + np.exp(-k * (t - t0)))


def _gompertz(t, L, k, t0):
    import numpy as np
    return L * np.exp(-np.exp(-k * (t - t0)))


def _fit_aic(cum: list[float], func) -> tuple[float, list[float]]:
    """网格初值 + 最小二乘拟合,返回 (AIC, 参数)。失败 → (inf, [])。"""
    try:
        import numpy as np
        from scipy.optimize import curve_fit
    except ImportError:
        return float("inf"), []

    t = np.arange(len(cum), dtype=float)
    y = np.asarray(cum, dtype=float)
    l_guess = max(cum) * 1.2
    best = (float("inf"), [])
    for k0 in (0.3, 0.6, 1.0):
        try:
            popt, _ = curve_fit(
                func, t, y, p0=[l_guess, k0, len(cum) / 2],
                bounds=([max(cum) * 0.9, 1e-3, -len(cum)], [max(cum) * 50, 5, 2 * len(cum)]),
                maxfev=20000,
            )
            ssr = float(np.sum((y - func(t, *popt)) ** 2))
            aic = len(cum) * math.log(max(ssr, 1e-12) / len(cum)) + 2 * 3
            if aic < best[0]:
                best = (aic, [float(v) for v in popt])
        except Exception:  # noqa: BLE001  拟合失败换初值
            continue
    return best


def s_curve_stage(ts: list[float], cum: list[float]) -> str:
    """累计序列 → emerging/growth/mature/saturated/insufficient。

    Logistic/Gompertz AIC 择优;阶段由 t_last 相对拐点 t0 与 N/N_L 位置定:
    - N < 0.2L → emerging;0.2L..0.8L → growth;>0.8L 且近 3 点导数降 → mature;
      导数近 0 → saturated。
    """
    if len(cum) < _MIN_CURVE_POINTS or max(cum) <= 0:
        return "insufficient"
    cum = [c if c > 0 else 1e-9 for c in cum]
    aic_log, p_log = _fit_aic(cum, _logistic)
    aic_gom, p_gom = _fit_aic(cum, _gompertz)
    if not p_log and not p_gom:
        return "insufficient"
    L, k, t0 = (p_log if aic_log <= aic_gom else p_gom)
    n_last = cum[-1]
    ratio = n_last / L if L > 0 else 0
    recent_growth = cum[-1] - cum[-4] if len(cum) >= 4 else cum[-1] - cum[0]
    if ratio < 0.2:
        return "emerging"
    if ratio < 0.8:
        return "growth"
    if recent_growth <= 0.01 * max(cum):
        return "saturated"
    return "mature"


# ── B3 TEM 象限 ──

def tem_quadrants(shares: dict[str, float],
                  growths: dict[str, float]) -> dict[str, str]:
    """对象份额/增速 → 象限标签。

    切点:x=全体份额均值,y=0(WISDOM 原设定)。
    strong(高份高增)/ weak(低份高增=弱信号)/ latent(低份低增)/ nswb(高份低增)。
    """
    if not shares:
        return {}
    x_cut = sum(shares.values()) / len(shares)
    out: dict[str, str] = {}
    for obj, share in shares.items():
        g = growths.get(obj, 0.0)
        hi_share = share > x_cut
        if g > 0 and hi_share:
            out[obj] = "strong"
        elif g > 0:
            out[obj] = "weak"
        elif hi_share:
            out[obj] = "nswb"
        else:
            out[obj] = "latent"
    return out


# ── B4 IPC 共类融合 ──

def salton(c_ab: int, n_a: int, n_b: int) -> float:
    """Salton = C_AB/√(N_A·N_B)。"""
    if n_a <= 0 or n_b <= 0:
        return 0.0
    return c_ab / math.sqrt(n_a * n_b)


def emerging_pairs(pairs_by_win: dict[int, dict[tuple[str, str], int]],
                   domain_counts_by_win: dict[int, dict[str, int]],
                   *, lookback_years: int = 3,
                   min_salton: float = 0.05) -> list[dict]:
    """逐年共类对计数 → 新兴跨域对列表。

    新对:首现年距最新窗 ≤ lookback_years;升:salton 比上年升。
    返回按 (is_new_pair, salton_rising, salton) 优先级过滤后的最新窗快照。
    """
    if not pairs_by_win:
        return []
    last_win = max(pairs_by_win)
    first_seen: dict[tuple[str, str], int] = {}
    for w in sorted(pairs_by_win):
        for pair in pairs_by_win[w]:
            first_seen.setdefault(pair, w)

    out: list[dict] = []
    prev_win = last_win - 1
    for pair, c in pairs_by_win[last_win].items():
        a, b = pair
        n_a = domain_counts_by_win.get(last_win, {}).get(a, 0)
        n_b = domain_counts_by_win.get(last_win, {}).get(b, 0)
        s = salton(c, n_a, n_b)
        if s < min_salton:
            continue
        c_prev = pairs_by_win.get(prev_win, {}).get(pair, 0)
        s_prev = salton(c_prev,
                        domain_counts_by_win.get(prev_win, {}).get(a, 0),
                        domain_counts_by_win.get(prev_win, {}).get(b, 0))
        is_new = (last_win - first_seen.get(pair, last_win)) < lookback_years
        rising = s > s_prev
        out.append({
            "object_id": f"{a}|{b}",
            "count": c,
            "salton": s,
            "first_seen": first_seen.get(pair, last_win),
            "is_new_pair": is_new,
            "salton_rising": rising,
        })
    # 只留值得关注的:新对或强度升
    out = [p for p in out if p["is_new_pair"] or p["salton_rising"]]
    out.sort(key=lambda p: (-int(p["is_new_pair"]), -p["salton"]))
    return out


def pair_combinations(subclasses: set[str]) -> list[tuple[str, str]]:
    """域集合 → 排序对组合(共类边)。"""
    return [tuple(sorted(c)) for c in combinations(sorted(subclasses), 2)]
