"""单元测试：topic_selection 服务（策略评分 + LLM 评审 + 融合 + 反馈闭环）。"""
from __future__ import annotations

from datetime import date
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.topic_selection.services.score_fusion import ScoreFusion, TopicCandidate


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_candidate(**kwargs) -> TopicCandidate:
    defaults = dict(
        topic_id="TOPIC_001",
        title="量子计算在密码学中的应用",
        summary="探讨量子计算对现有密码体系的影响",
        related_tech_ids=["TECH_001"],
        related_org_ids=["ORG_001"],
        related_project_ids=[],
        related_policy_refs=[],
        score_hot=0.8,
        score_policy=0.6,
        score_impact=0.7,
        score_dedup=0.9,
        score_llm_gen=0.75,
        review_novelty=0.8,
        review_importance=0.9,
        review_feasibility=0.7,
        review_expression=0.85,
        review_evidence="技术新颖，政策关注高",
        final_score=0.0,
    )
    defaults.update(kwargs)
    return TopicCandidate(**defaults)


def _make_aggregated():
    from metaprofile.topic_selection.services.input_aggregator import AggregatedInput
    return AggregatedInput(
        frontier_techs=[
            {"tech_name": "量子计算", "fusion_score": 0.85},
            {"tech_name": "人工智能", "fusion_score": 0.72},
        ],
        policy_keywords=["量子", "密码", "国防"],
        period_from=date(2026, 1, 1),
        period_to=date(2026, 1, 31),
    )


# ─── ScoreFusion ─────────────────────────────────────────────────────────────

class TestScoreFusion:
    def _fusion(self) -> ScoreFusion:
        return ScoreFusion()

    def test_fuse_all_max(self):
        f = self._fusion()
        c = _make_candidate(
            score_hot=1.0, score_policy=1.0, score_impact=1.0,
            score_dedup=1.0, score_llm_gen=1.0,
            review_novelty=1.0, review_importance=1.0,
            review_feasibility=1.0, review_expression=1.0,
        )
        result = f.fuse(c)
        assert abs(result - 1.0) < 1e-6

    def test_fuse_all_zero(self):
        f = self._fusion()
        c = _make_candidate(
            score_hot=0.0, score_policy=0.0, score_impact=0.0,
            score_dedup=0.0, score_llm_gen=0.0,
            review_novelty=0.0, review_importance=0.0,
            review_feasibility=0.0, review_expression=0.0,
        )
        result = f.fuse(c)
        assert result == 0.0

    def test_strategy_weights_sum_to_one(self):
        w = ScoreFusion.DEFAULT_STRATEGY_WEIGHTS
        assert abs(sum(w.values()) - 1.0) < 1e-6

    def test_review_weights_sum_to_one(self):
        w = ScoreFusion.DEFAULT_REVIEW_WEIGHTS
        assert abs(sum(w.values()) - 1.0) < 1e-6

    def test_strategy_review_split(self):
        a, b = ScoreFusion.STRATEGY_VS_REVIEW
        assert abs(a + b - 1.0) < 1e-6
        assert a == 0.6
        assert b == 0.4

    def test_fuse_partial(self):
        f = self._fusion()
        c = _make_candidate(
            score_hot=1.0, score_policy=0.0, score_impact=0.0,
            score_dedup=0.0, score_llm_gen=0.0,
            review_novelty=0.0, review_importance=0.0,
            review_feasibility=0.0, review_expression=0.0,
        )
        result = f.fuse(c)
        # strategy_score = 0.25 * 1.0 = 0.25; review_score = 0.0
        # final = 0.6 * 0.25 + 0.4 * 0.0 = 0.15
        assert abs(result - 0.15) < 1e-6


# ─── HotStrategyScorer ───────────────────────────────────────────────────────

class TestHotStrategyScorer:
    def test_score_with_matching_tech(self):
        from metaprofile.topic_selection.services.strategy_hot import HotStrategyScorer
        scorer = HotStrategyScorer()
        agg = _make_aggregated()
        result = scorer.score("量子计算密码学", agg)
        assert 0.0 <= result <= 1.0
        assert result > 0.0  # "量子" matches

    def test_score_no_frontier_techs(self):
        from metaprofile.topic_selection.services.input_aggregator import AggregatedInput
        from metaprofile.topic_selection.services.strategy_hot import HotStrategyScorer
        scorer = HotStrategyScorer()
        agg = AggregatedInput()
        result = scorer.score("量子计算", agg)
        assert result == 0.0

    def test_score_no_match_returns_fallback(self):
        from metaprofile.topic_selection.services.strategy_hot import HotStrategyScorer
        scorer = HotStrategyScorer()
        agg = _make_aggregated()
        result = scorer.score("XYZXYZ完全不匹配的标题", agg)
        assert 0.0 <= result <= 1.0


# ─── PolicyStrategyScorer ─────────────────────────────────────────────────────

class TestPolicyStrategyScorer:
    def test_score_with_keyword_match(self):
        from metaprofile.topic_selection.services.strategy_policy import PolicyStrategyScorer
        scorer = PolicyStrategyScorer()
        agg = _make_aggregated()
        result = scorer.score("量子密码技术分析", agg)
        assert result > 0.0

    def test_score_no_keywords(self):
        from metaprofile.topic_selection.services.input_aggregator import AggregatedInput
        from metaprofile.topic_selection.services.strategy_policy import PolicyStrategyScorer
        scorer = PolicyStrategyScorer()
        agg = AggregatedInput(policy_keywords=[])
        result = scorer.score("量子计算", agg)
        assert result == 0.0

    def test_score_capped_at_one(self):
        from metaprofile.topic_selection.services.input_aggregator import AggregatedInput
        from metaprofile.topic_selection.services.strategy_policy import PolicyStrategyScorer
        scorer = PolicyStrategyScorer()
        kws = ["a", "b", "c", "d"]
        agg = AggregatedInput(policy_keywords=kws)
        result = scorer.score("a b c d e", agg)
        assert result <= 1.0


# ─── DedupStrategyScorer ─────────────────────────────────────────────────────

class TestDedupStrategyScorer:
    @pytest.mark.asyncio
    async def test_score_no_history_returns_one(self):
        from metaprofile.topic_selection.services.strategy_dedup import DedupStrategyScorer
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        scorer = DedupStrategyScorer(mock_db)
        result = await scorer.score("量子计算研究")
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_score_identical_history_returns_zero(self):
        from metaprofile.topic_selection.services.strategy_dedup import DedupStrategyScorer
        mock_db = AsyncMock()
        mock_result = MagicMock()
        title = "量子计算研究"
        mock_result.all.return_value = [(title,)]
        mock_db.execute = AsyncMock(return_value=mock_result)
        scorer = DedupStrategyScorer(mock_db)
        result = await scorer.score(title)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_score_db_error_returns_one(self):
        from metaprofile.topic_selection.services.strategy_dedup import DedupStrategyScorer
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB error")
        scorer = DedupStrategyScorer(mock_db)
        result = await scorer.score("量子计算研究")
        assert result == 1.0


# ─── ImpactStrategyScorer ────────────────────────────────────────────────────

class TestImpactStrategyScorer:
    @pytest.mark.asyncio
    async def test_score_returns_zero_on_error(self):
        from metaprofile.topic_selection.services.strategy_impact import ImpactStrategyScorer
        scorer = ImpactStrategyScorer()
        with patch("httpx.AsyncClient", side_effect=Exception("timeout")):
            result = await scorer.score("量子计算", None)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_score_capped_at_one(self):
        from metaprofile.topic_selection.services.strategy_impact import ImpactStrategyScorer, _ORG_MAX, _PROJ_MAX
        scorer = ImpactStrategyScorer()
        org_resp = MagicMock()
        org_resp.status_code = 200
        org_resp.json.return_value = {"total": int(_ORG_MAX * 10), "items": []}
        proj_resp = MagicMock()
        proj_resp.status_code = 200
        proj_resp.json.return_value = {"total": int(_PROJ_MAX * 10), "items": []}

        call_count = 0
        async def _post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return org_resp if call_count == 1 else proj_resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = _post
            mock_cls.return_value = mock_client
            result = await scorer.score("量子计算", "信息技术")
        assert result <= 1.0


# ─── LLMReviewer ─────────────────────────────────────────────────────────────

class TestLLMReviewer:
    @pytest.mark.asyncio
    async def test_review_returns_score(self):
        from metaprofile.topic_selection.services.llm_reviewer import LLMReviewer, TopicReviewScore
        mock_gateway = MagicMock()
        reviewer = LLMReviewer(mock_gateway)
        expected = TopicReviewScore(
            novelty=0.8, importance=0.9, feasibility=0.7,
            expression=0.85, evidence="技术新颖"
        )
        with patch(
            "metaprofile.topic_selection.services.llm_reviewer.call_with_schema",
            new_callable=AsyncMock,
            return_value=(expected, {}),
        ):
            result = await reviewer.review(title="量子计算", summary="量子计算概述")
        assert 0.0 <= result.novelty <= 1.0
        assert 0.0 <= result.importance <= 1.0
        assert 0.0 <= result.feasibility <= 1.0
        assert 0.0 <= result.expression <= 1.0


# ─── FeedbackLoopService ─────────────────────────────────────────────────────

class TestFeedbackLoopService:
    @pytest.mark.asyncio
    async def test_record_creates_feedback(self):
        from metaprofile.topic_selection.services.feedback_loop import FeedbackLoopService
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.get = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        svc = FeedbackLoopService(mock_db)
        feedback = await svc.record(
            topic_id="TOPIC_001",
            rating="accept",
            score=4,
            comments="很好",
            operator="alice",
        )
        assert feedback.topic_id == "TOPIC_001"
        assert feedback.rating == "accept"
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_compute_acceptance_rate_no_feedback(self):
        from metaprofile.topic_selection.services.feedback_loop import FeedbackLoopService
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_result)

        svc = FeedbackLoopService(mock_db)
        rate = await svc.compute_acceptance_rate()
        assert rate == 0.0

    @pytest.mark.asyncio
    async def test_compute_acceptance_rate_db_error(self):
        from metaprofile.topic_selection.services.feedback_loop import FeedbackLoopService
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB error")
        svc = FeedbackLoopService(mock_db)
        rate = await svc.compute_acceptance_rate()
        assert rate == 0.0


# ─── LLMRagStrategyScorer ────────────────────────────────────────────────────

class TestLLMRagStrategyScorer:
    @pytest.mark.asyncio
    async def test_generate_returns_empty_on_error(self):
        from metaprofile.topic_selection.services.strategy_llm_rag import LLMRagStrategyScorer
        mock_gateway = MagicMock()
        scorer = LLMRagStrategyScorer(mock_gateway)
        agg = _make_aggregated()
        with patch(
            "metaprofile.topic_selection.services.strategy_llm_rag.call_with_schema",
            new_callable=AsyncMock,
            side_effect=Exception("LLM unavailable"),
        ):
            result = await scorer.generate(agg, target_count=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_returns_suggestions(self):
        from metaprofile.topic_selection.services.strategy_llm_rag import (
            LLMRagStrategyScorer, TopicSuggestion, TopicSuggestions
        )
        mock_gateway = MagicMock()
        scorer = LLMRagStrategyScorer(mock_gateway)
        agg = _make_aggregated()
        suggestions = TopicSuggestions(topics=[
            TopicSuggestion(title="量子密码新进展", summary="探讨量子密码", confidence=0.85),
        ])
        with patch(
            "metaprofile.topic_selection.services.strategy_llm_rag.call_with_schema",
            new_callable=AsyncMock,
            return_value=(suggestions, {}),
        ):
            result = await scorer.generate(agg, target_count=1)
        assert len(result) == 1
        assert result[0].title == "量子密码新进展"
