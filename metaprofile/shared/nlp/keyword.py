"""关键词提取：TF-IDF 与 TextRank（基于 jieba.analyse）。"""
from __future__ import annotations

import jieba.analyse


def extract_tfidf(
    text: str,
    *,
    top_k: int = 20,
    allow_pos: tuple[str, ...] = ("ns", "n", "vn", "v", "nr"),
) -> list[tuple[str, float]]:
    """TF-IDF 关键词提取。返回 [(词, 权重)] 降序。"""
    results = jieba.analyse.extract_tags(
        text, topK=top_k, withWeight=True, allowPOS=allow_pos
    )
    return [(str(w), float(s)) for w, s in results]


def extract_textrank(
    text: str,
    *,
    top_k: int = 20,
    allow_pos: tuple[str, ...] = ("ns", "n", "vn", "v"),
) -> list[tuple[str, float]]:
    """TextRank 关键词提取。返回 [(词, 权重)] 降序。"""
    results = jieba.analyse.textrank(
        text, topK=top_k, withWeight=True, allowPOS=allow_pos
    )
    return [(str(w), float(s)) for w, s in results]


def keywords_only(pairs: list[tuple[str, float]]) -> list[str]:
    return [w for w, _ in pairs]


def extract_keywords(
    text: str,
    *,
    top_k: int = 20,
    method: str = "tfidf",
) -> list[str]:
    """便捷接口：直接返回关键词列表（不含权重）。method: 'tfidf' | 'textrank'。"""
    if method == "textrank":
        pairs = extract_textrank(text, top_k=top_k)
    else:
        pairs = extract_tfidf(text, top_k=top_k)
    return keywords_only(pairs)
