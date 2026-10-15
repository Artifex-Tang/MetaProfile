"""Phase A3/A4/A5:计数语义(df 非 presence)+ 证据选择 + 共现边 纯函数测试。"""
from __future__ import annotations

from datetime import date

from metaprofile.new_tech_discovery.services.corpus_loader import CorpusDoc
from metaprofile.new_tech_discovery.services.evidence_builder import (
    cooccurrence_pairs,
    select_evidence,
)
from metaprofile.new_tech_discovery.services.signal_metrics import (
    build_term_stats,
    build_windows,
)


def _stats_for(docs, **kw):
    windows = build_windows(
        date(2026, 1, 1), date(2026, 3, 31), lookback_months=0, window_months=1,
    )
    return build_term_stats(docs, windows, **kw)


def test_df_by_window_counts_documents():
    """同窗 3 篇含 quantum → df=3(原 presence 语义恒 1,G8 修复)。"""
    docs = [
        CorpusDoc("science", str(i), "quantum research", date(2026, 1, 10), [])
        for i in range(3)
    ]
    q = next(s for s in _stats_for(docs, min_df=1) if s.term == "quantum")
    assert q.df_by_window[0] == 3


def test_df_by_source_window_counts():
    """同窗同源 2 篇 → df_by_source_window 计 2(原恒 1)。"""
    docs = [
        CorpusDoc("science", "a", "quantum", date(2026, 1, 5), []),
        CorpusDoc("science", "b", "quantum", date(2026, 1, 20), []),
    ]
    q = next(s for s in _stats_for(docs, min_df=1) if s.term == "quantum")
    assert q.df_by_source_window[0] == {"science": 2}


def test_term_docs_capped_and_most_recent_first():
    """doc_ids 截断到 doc_cap 且按时间戳降序(最近在前,审查 H2)。"""
    docs = [
        CorpusDoc("science", "old", "quantum", date(2026, 1, 1), []),
        CorpusDoc("science", "mid", "quantum", date(2026, 2, 1), []),
        CorpusDoc("science", "new", "quantum", date(2026, 3, 1), []),
        CorpusDoc("science", "newest", "quantum", date(2026, 3, 20), []),
    ]
    q = next(s for s in _stats_for(docs, min_df=1, doc_cap=2) if s.term == "quantum")
    assert len(q.doc_ids) == 2
    assert q.doc_ids == ["newest", "new"]  # 最近的 2 篇,降序
    assert q.df_by_window[0] == 1 and sum(q.df_by_window) == 4  # 统计不受截断影响


def test_select_evidence_takes_head_of_recency_order():
    """doc_ids 已是最近在前 → 取前 cap。"""
    assert select_evidence(["newest", "new", "mid"], cap=2) == ["newest", "new"]
    assert select_evidence(["a"], cap=3) == ["a"]
    assert select_evidence([], cap=3) == []


def test_cooccurrence_pairs_counts_codoc():
    """同文档共现的信号词对 → 权重=共文档数;无共现不产边。"""
    docs_terms = [
        {"quantum", "chip", "noise"},
        {"quantum", "chip"},
        {"quantum", "sensor"},
    ]
    weights = cooccurrence_pairs(docs_terms, signal_terms={"quantum", "chip", "sensor"})
    assert weights[("chip", "quantum")] == 2
    assert weights[("quantum", "sensor")] == 1
    assert ("noise", "quantum") not in weights  # 非信号词不成边


def test_cooccurrence_pairs_ignores_docs_with_lt_2_signal_terms():
    weights = cooccurrence_pairs([{"quantum"}], signal_terms={"quantum", "chip"})
    assert weights == {}


def test_apply_source_weights_discounts_finance_sources():
    """研报/新闻源 df 降权(diversity 前应用),未知源 1.0。"""
    from metaprofile.new_tech_discovery.services.signal_metrics import (
        apply_source_weights,
        diversity_score,
    )
    raw = {"science": 10, "industry_report": 10, "patent": 10}
    w = apply_source_weights(raw)
    assert w == {"science": 10, "industry_report": 4, "patent": 10}
    # 全研报单源 → 仍 0(单源无多样性)
    assert diversity_score(apply_source_weights({"industry_report": 100})) == 0.0


def test_finance_stopwords_filtered():
    from metaprofile.new_tech_discovery.services.signal_metrics import tokenize
    toks = tokenize("深成指成交额走强,量子芯片突破")
    assert "深成指" not in toks and "成交额" not in toks
    assert "量子芯片" in toks or "量子" in toks
