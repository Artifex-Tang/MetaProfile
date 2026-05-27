"""
选题生成五策略与综合评分。

策略 A：技术热度排序（基于 scan_monitor 的前沿技术清单）
策略 B：政策关联匹配（与近期发布政策匹配度）
策略 C：产业影响力评估（基于画像层 org / enterprise / project 关联度）
策略 D：历史选题去重（与历史选题库相似度）
策略 E：LLM RAG 多角度生成（生成式补充）

LLM 评审员 4 维度：新颖性 / 重要性 / 可行性 / 表达
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TopicCandidate:
    topic_id: str
    title: str
    summary: str
    related_tech_ids: list[str]
    related_org_ids: list[str]
    related_project_ids: list[str]
    related_policy_refs: list[str]

    score_hot: float          # 策略 A
    score_policy: float       # 策略 B
    score_impact: float       # 策略 C
    score_dedup: float        # 策略 D（越大越独特）
    score_llm_gen: float      # 策略 E

    review_novelty: float     # LLM 评审 - 新颖性
    review_importance: float  # LLM 评审 - 重要性
    review_feasibility: float # LLM 评审 - 可行性
    review_expression: float  # LLM 评审 - 表达
    review_evidence: str

    final_score: float


class ScoreFusion:
    DEFAULT_STRATEGY_WEIGHTS = {
        "hot": 0.25,
        "policy": 0.20,
        "impact": 0.20,
        "dedup": 0.15,
        "llm_gen": 0.20,
    }

    DEFAULT_REVIEW_WEIGHTS = {
        "novelty": 0.30,
        "importance": 0.30,
        "feasibility": 0.20,
        "expression": 0.20,
    }

    # 策略综合分 vs LLM 评审分 的权重
    STRATEGY_VS_REVIEW = (0.6, 0.4)

    def fuse(self, candidate: TopicCandidate) -> float:
        sw = self.DEFAULT_STRATEGY_WEIGHTS
        rw = self.DEFAULT_REVIEW_WEIGHTS
        strategy_score = (
            sw["hot"] * candidate.score_hot
            + sw["policy"] * candidate.score_policy
            + sw["impact"] * candidate.score_impact
            + sw["dedup"] * candidate.score_dedup
            + sw["llm_gen"] * candidate.score_llm_gen
        )
        review_score = (
            rw["novelty"] * candidate.review_novelty
            + rw["importance"] * candidate.review_importance
            + rw["feasibility"] * candidate.review_feasibility
            + rw["expression"] * candidate.review_expression
        )
        a, b = self.STRATEGY_VS_REVIEW
        return a * strategy_score + b * review_score
