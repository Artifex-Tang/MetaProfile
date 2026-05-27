"""单元测试：shared/nlp 模块（无外部依赖）。"""
from __future__ import annotations

import pytest

from metaprofile.shared.nlp.burst_detection import BurstResult, compute_burst_scores
from metaprofile.shared.nlp.keyword import extract_keywords, extract_tfidf
from metaprofile.shared.nlp.tokenizer import get_tokenizer


# ─── tokenizer ──────────────────────────────────────────────────────────────

def test_tokenize_basic():
    t = get_tokenizer()
    tokens = t.tokenize("量子计算技术发展迅速")
    assert isinstance(tokens, list)
    assert len(tokens) > 0
    assert all(isinstance(tok, str) for tok in tokens)


def test_tokenize_empty():
    t = get_tokenizer()
    assert t.tokenize("") == []


def test_tokenize_for_search():
    t = get_tokenizer()
    tokens = t.tokenize_for_search("自然语言处理")
    assert len(tokens) >= 2


def test_add_words():
    t = get_tokenizer()
    t.add_words(["量子纠错码"])
    tokens = t.tokenize("量子纠错码技术")
    assert "量子纠错码" in tokens


# ─── keyword ────────────────────────────────────────────────────────────────

TEXT = (
    "量子计算是利用量子力学原理进行计算的技术。"
    "量子比特可以同时处于0和1的叠加态，使量子计算机在某些问题上远超经典计算机。"
    "目前量子计算的主要挑战是量子纠错和量子退相干问题。"
)


def test_extract_tfidf_returns_pairs():
    pairs = extract_tfidf(TEXT, top_k=5)
    assert len(pairs) <= 5
    for w, s in pairs:
        assert isinstance(w, str)
        assert s > 0.0  # TF-IDF 权重为正值，不保证 <=1.0


def test_extract_keywords_tfidf():
    kws = extract_keywords(TEXT, top_k=5, method="tfidf")
    assert isinstance(kws, list)
    assert 1 <= len(kws) <= 5


def test_extract_keywords_textrank():
    kws = extract_keywords(TEXT, top_k=5, method="textrank")
    assert isinstance(kws, list)
    assert 1 <= len(kws) <= 5


# ─── burst_detection ────────────────────────────────────────────────────────

def test_burst_empty():
    assert compute_burst_scores([]) == []


def test_burst_single_slot():
    result = compute_burst_scores([{"量子计算": 10}])
    assert isinstance(result, list)


def test_burst_detects_spike():
    time_series = [
        {"量子计算": 1, "人工智能": 5},
        {"量子计算": 1, "人工智能": 5},
        {"量子计算": 1, "人工智能": 5},
        {"量子计算": 1, "人工智能": 5},
        {"量子计算": 20, "人工智能": 5},  # 量子计算突增
    ]
    results = compute_burst_scores(time_series, recent_window=1, burst_threshold=2.0)
    bursting = {r.keyword for r in results if r.is_bursting}
    assert "量子计算" in bursting
    assert "人工智能" not in bursting


def test_burst_min_count_filter():
    time_series = [{"罕见词": 1}, {"量子计算": 5}]
    results = compute_burst_scores(time_series, min_total_count=3)
    keywords = {r.keyword for r in results}
    assert "罕见词" not in keywords


def test_burst_sorted_descending():
    time_series = [
        {"A": 1, "B": 5},
        {"A": 10, "B": 5},
    ]
    results = compute_burst_scores(time_series, min_total_count=1)
    scores = [r.burst_score for r in results]
    assert scores == sorted(scores, reverse=True)
