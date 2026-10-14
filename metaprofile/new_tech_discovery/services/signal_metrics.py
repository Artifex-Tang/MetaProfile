"""弱信号维度纯函数（专利技术方案 §4 公式）。

全部纯函数、无 IO、无随机 —— 便于 TDD 与发明专利复现。
"""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta


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


# ── 预处理 + 窗口化（语料 → 候选词项统计）──

_CN_STOPWORDS = {
    "的", "了", "和", "与", "在", "是", "为", "及", "等", "对", "中", "或",
    "一种", "一个", "本",
}
_EN_STOPWORDS = {
    "the", "a", "an", "is", "are", "of", "and", "to", "in",
    "on", "for", "with", "as", "by", "at",
}
_JIEBA_AVAILABLE = False
try:
    import jieba  # type: ignore
    _JIEBA_AVAILABLE = True
except ImportError:  # jieba 缺失 → 中文退回正则切字/词
    jieba = None  # type: ignore


def _detect_lang(text: str) -> str:
    for ch in text:
        if "一" <= ch <= "鿿":
            return "zh"
    return "en"


def tokenize(text: str, lang: str | None = None) -> list[str]:
    """分词 + 停用词过滤（§3.3）。中文 jieba（缺失退正则）、英文小写+词形。"""
    if not text:
        return []
    lang = lang or _detect_lang(text)
    if lang == "zh":
        if _JIEBA_AVAILABLE:
            toks = [t.strip() for t in jieba.cut(text) if t.strip()]
        else:
            toks = re.findall(r"[一-鿿]{2,}|[A-Za-z]+", text)
        stop = _CN_STOPWORDS
    else:
        toks = re.findall(r"[a-z]+", text.lower())
        stop = _EN_STOPWORDS
    return [t for t in toks if t not in stop and len(t) > 1]


@dataclass
class Window:
    label: str
    start: date
    end: date
    is_history: bool


def build_windows(period_from, period_to, *, lookback_months, window_months) -> list[Window]:
    """构建月度窗口序列（历史 + 当前），时间顺序。每窗 = window_months 个自然月。"""
    def _month_floor(d: date) -> date:
        return d.replace(day=1)

    def _add_months(d: date, n: int) -> date:
        idx = d.year * 12 + (d.month - 1) + n
        y, m = divmod(idx, 12)
        return date(y, m + 1, 1)

    cur = _add_months(_month_floor(period_from), -lookback_months)
    end_hard = _month_floor(period_to)
    windows: list[Window] = []
    while cur <= end_hard:
        w_start = cur
        w_end_last = _add_months(cur, window_months) - timedelta(days=1)
        is_hist = cur < _month_floor(period_from)
        windows.append(Window(label=cur.strftime("%Y-%m"), start=w_start,
                               end=w_end_last, is_history=is_hist))
        cur = _add_months(cur, window_months)
    return windows


@dataclass
class TermStats:
    term: str
    df_by_window: list[int]                      # 每窗文档频（计数），时间顺序（对齐 windows）
    df_by_source: dict[str, int]                 # 当前期内按源文档频（计数）
    df_by_source_window: list[dict[str, int]]    # 每窗按源文档频（计数，coherence 用）
    is_entity: bool
    tf_by_window: list[int] | None = None        # 每窗词频（出现次数，term_stats 持久化用）
    # 命中文档 id，**按时间戳降序（最近在前）**，截断到 doc_cap（证据回填用，
    # 审查 H2:不得按加载序取"最近"）
    doc_ids: list[str] | None = None


def _to_date(ts) -> date:
    """ts 可能是 date 或 datetime → 统一转 date（T6 reviewer S1）。"""
    if isinstance(ts, datetime):
        return ts.date()
    return ts


def _window_index(ts, windows: list[Window]) -> int | None:
    d = _to_date(ts)
    for i, w in enumerate(windows):
        if w.start <= d <= w.end:
            return i
    return None


def build_term_stats(docs, windows: list[Window], *, min_df: int = 2,
                     doc_cap: int = 40) -> list[TermStats]:
    """语料 + 窗口 → 每候选词项的窗口/源统计。

    【2026-10-14 G8 修复】df/tf 全部为**计数**（原 presence 常量 1 → coherence
    只能测 0→1 涌现）。doc_ids 按**时间戳降序**截断到 doc_cap（证据回填取最近
    篇，统计不受截断影响）。min_df 过滤极低频噪声（默认 ≥2）。

    【审查 M6】窗口计数用稀疏 dict[wi] 存储（多数术语只出现在少数窗，
    稠密 list×百万词表会到 GB 级）。
    """
    # term → {wi: df} / {wi: {source: df}} / {wi: tf} / [(ts, doc_id)]（截断）
    term_df: dict[str, dict[int, int]] = {}
    term_sw: dict[str, dict[int, dict[str, int]]] = {}
    term_tf: dict[str, dict[int, int]] = {}
    term_docs: dict[str, list[tuple[date, str]]] = {}
    term_is_entity: dict[str, bool] = {}

    def _hit(term: str, wi: int, source: str, tf: int,
             ts: date, doc_id: str) -> None:
        if term not in term_df:
            term_df[term] = {}
            term_sw[term] = {}
            term_tf[term] = {}
            term_docs[term] = []
            term_is_entity[term] = False
        term_df[term][wi] = term_df[term].get(wi, 0) + 1
        swd = term_sw[term].setdefault(wi, {})
        swd[source] = swd.get(source, 0) + 1
        term_tf[term][wi] = term_tf[term].get(wi, 0) + tf
        docs_list = term_docs[term]
        if len(docs_list) < doc_cap:
            docs_list.append((ts, doc_id))
        else:
            # 已满:只保留更新的(逐个找最小换入;cap 小,O(cap) 可接受)
            min_i = min(range(len(docs_list)), key=lambda i: docs_list[i][0])
            if ts > docs_list[min_i][0]:
                docs_list[min_i] = (ts, doc_id)

    for doc in docs:
        wi = _window_index(doc.timestamp, windows)
        if wi is None:
            continue
        toks = tokenize(doc.text)
        ent_tok = set(doc.entities or [])
        terms_here = set(toks) | {e for e in ent_tok if len(e) > 1}
        tf_here: dict[str, int] = {}
        for t in toks:
            tf_here[t] = tf_here.get(t, 0) + 1
        d = _to_date(doc.timestamp)
        for term in terms_here:
            _hit(term, wi, doc.source, tf_here.get(term, 1), d, doc.doc_id)
            if term in ent_tok:
                term_is_entity[term] = True

    n_win = len(windows)
    stats: list[TermStats] = []
    for term, df_sparse in term_df.items():
        df_by_window = [df_sparse.get(i, 0) for i in range(n_win)]
        total_df = sum(df_by_window)
        if total_df < min_df:
            continue
        sw_sparse = term_sw[term]
        df_by_source: dict[str, int] = {}
        for i, w in enumerate(windows):
            if w.is_history:
                continue
            for s, c in sw_sparse.get(i, {}).items():
                df_by_source[s] = df_by_source.get(s, 0) + c
        tf_sparse = term_tf[term]
        # 证据 doc_ids:统一按时间戳降序(最近在前)
        recent_docs = sorted(
            term_docs[term], key=lambda x: x[0], reverse=True,
        )
        stats.append(TermStats(
            term=term, df_by_window=df_by_window,
            df_by_source=df_by_source,
            df_by_source_window=[dict(sw_sparse.get(i, {})) for i in range(n_win)],
            is_entity=term_is_entity[term],
            tf_by_window=[tf_sparse.get(i, 0) for i in range(n_win)],
            doc_ids=[doc_id for _, doc_id in recent_docs],
        ))
    return stats
