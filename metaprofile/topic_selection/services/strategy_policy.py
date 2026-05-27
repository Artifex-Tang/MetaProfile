"""策略 B：政策关联匹配。

比较选题标题与政策关键词集合的词汇覆盖率，评估政策契合度。
"""
from __future__ import annotations

from metaprofile.topic_selection.services.input_aggregator import AggregatedInput


class PolicyStrategyScorer:
    """政策关联策略评分器。"""

    def score(self, title: str, aggregated: AggregatedInput) -> float:
        """返回 [0, 1] 政策匹配分：关键词命中比例。"""
        keywords = aggregated.policy_keywords
        if not keywords:
            return 0.0
        title_lower = title.lower()
        hits = sum(1 for kw in keywords if kw.lower() in title_lower)
        return min(hits / max(len(keywords), 1), 1.0)
