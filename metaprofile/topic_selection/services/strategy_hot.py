"""策略 A：技术热度排序。

基于 scan_monitor 前沿技术融合分，计算候选选题的热度得分。
"""
from __future__ import annotations

from metaprofile.topic_selection.services.input_aggregator import AggregatedInput


class HotStrategyScorer:
    """技术热度策略评分器。"""

    def score(self, title: str, aggregated: AggregatedInput) -> float:
        """返回 [0, 1] 热度分：取前沿技术清单中最高融合分作为代理。"""
        if not aggregated.frontier_techs:
            return 0.0
        best = 0.0
        title_lower = title.lower()
        for ft in aggregated.frontier_techs:
            name = (ft.get("tech_name") or "").lower()
            if not name:
                continue
            # 标题与技术名称有词汇重叠时，取其融合分
            overlap = any(word in title_lower for word in name.split() if len(word) > 1)
            if overlap:
                fs = float(ft.get("fusion_score") or 0.0)
                if fs > best:
                    best = fs
        # 无命中时取全局均值
        if best == 0.0:
            scores = [float(ft.get("fusion_score") or 0.0) for ft in aggregated.frontier_techs]
            best = sum(scores) / len(scores) * 0.5
        return min(best, 1.0)
