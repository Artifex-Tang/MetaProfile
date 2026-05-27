"""单元测试：scan_monitor 信号服务 + 融合评分 + LLM 验证 + TRL 标注。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.scan_monitor.services.fusion_scorer import FrontierTechFusionScorer
from metaprofile.scan_monitor.services.llm_agent_validator import FrontierAgentValidator, FrontierAgentVerdict
from metaprofile.scan_monitor.services.trl_annotator import TRLAnnotation, TRLAnnotator


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_period() -> tuple[date, date]:
    return date(2026, 1, 1), date(2026, 1, 31)


# ─── FrontierTechFusionScorer ─────────────────────────────────────────────────

class TestFrontierTechFusionScorer:
    def _scorer(self) -> FrontierTechFusionScorer:
        return FrontierTechFusionScorer()

    def test_fuse_all_max(self):
        s = self._scorer()
        result = s.fuse(burst=1.0, patent=1.0, citation=1.0, invest=1.0, policy=1.0)
        assert abs(result - 1.0) < 1e-6

    def test_fuse_all_zero(self):
        s = self._scorer()
        result = s.fuse(burst=0.0, patent=0.0, citation=0.0, invest=0.0, policy=0.0)
        assert result == 0.0

    def test_fuse_default_weights_sum(self):
        w = FrontierTechFusionScorer.DEFAULT_WEIGHTS
        assert abs(sum(w.values()) - 1.0) < 1e-6

    def test_fuse_partial_signals(self):
        s = self._scorer()
        result = s.fuse(burst=1.0, patent=0.0, citation=0.0, invest=0.0, policy=0.0)
        assert abs(result - 0.20) < 1e-6

    def test_fuse_custom_weights(self):
        s = self._scorer()
        weights = {"burst": 1.0, "patent": 0.0, "citation": 0.0, "invest": 0.0, "policy": 0.0}
        result = s.fuse(burst=0.5, patent=1.0, citation=1.0, invest=1.0, policy=1.0, weights=weights)
        assert abs(result - 0.5) < 1e-6

    def test_fuse_intermediate(self):
        s = self._scorer()
        result = s.fuse(burst=0.5, patent=0.5, citation=0.5, invest=0.5, policy=0.5)
        assert abs(result - 0.5) < 1e-6


# ─── BurstSignalScorer ────────────────────────────────────────────────────────

class TestBurstSignalScorer:
    @pytest.mark.asyncio
    async def test_score_returns_zero_on_http_error(self):
        from metaprofile.scan_monitor.services.signal_burst import BurstSignalScorer
        scorer = BurstSignalScorer()
        pf, pt = _make_period()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子计算", domain=None, period_from=pf, period_to=pt)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_score_empty_items(self):
        from metaprofile.scan_monitor.services.signal_burst import BurstSignalScorer
        scorer = BurstSignalScorer()
        pf, pt = _make_period()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": [], "total": 0}
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子计算", domain=None, period_from=pf, period_to=pt)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_score_exception_returns_zero(self):
        from metaprofile.scan_monitor.services.signal_burst import BurstSignalScorer
        scorer = BurstSignalScorer()
        pf, pt = _make_period()
        with patch("httpx.AsyncClient", side_effect=Exception("conn refused")):
            result = await scorer.score(tech_name="量子计算", domain=None, period_from=pf, period_to=pt)
        assert result == 0.0


# ─── PatentSignalScorer ───────────────────────────────────────────────────────

class TestPatentSignalScorer:
    @pytest.mark.asyncio
    async def test_score_returns_zero_on_http_error(self):
        from metaprofile.scan_monitor.services.signal_patent import PatentSignalScorer
        scorer = PatentSignalScorer()
        pf, pt = _make_period()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子", domain=None, period_from=pf, period_to=pt)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_score_no_baseline(self):
        """recent=0, baseline=0 → returns 0."""
        from metaprofile.scan_monitor.services.signal_patent import PatentSignalScorer
        scorer = PatentSignalScorer()
        pf, pt = _make_period()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"total": 0}
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子", domain=None, period_from=pf, period_to=pt)
        assert result == 0.0


# ─── CitationSignalScorer ─────────────────────────────────────────────────────

class TestCitationSignalScorer:
    @pytest.mark.asyncio
    async def test_score_exception_returns_zero(self):
        from metaprofile.scan_monitor.services.signal_citation import CitationSignalScorer
        scorer = CitationSignalScorer()
        pf, pt = _make_period()
        with patch("httpx.AsyncClient", side_effect=Exception("timeout")):
            result = await scorer.score(tech_name="量子", domain=None, period_from=pf, period_to=pt)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_score_high_citations(self):
        from metaprofile.scan_monitor.services.signal_citation import CitationSignalScorer, _HIGH_CITATION_THRESHOLD, _MIN_CLUSTER_SIZE
        scorer = CitationSignalScorer()
        pf, pt = _make_period()

        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {"items": [{"tech_id": "TECH_001"}]}

        detail_resp = MagicMock()
        detail_resp.status_code = 200
        detail_resp.json.return_value = {
            "academic_outputs": [
                {"citations": _HIGH_CITATION_THRESHOLD},
                {"citations": _HIGH_CITATION_THRESHOLD + 10},
                {"citations": _HIGH_CITATION_THRESHOLD + 20},
            ]
        }

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=search_resp)
            mock_client.get = AsyncMock(return_value=detail_resp)
            mock_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子", domain=None, period_from=pf, period_to=pt)
        assert result == 1.0  # 3 / _MIN_CLUSTER_SIZE(3) = 1.0


# ─── InvestSignalScorer ───────────────────────────────────────────────────────

class TestInvestSignalScorer:
    @pytest.mark.asyncio
    async def test_score_invest_capped_at_one(self):
        from metaprofile.scan_monitor.services.signal_invest import InvestSignalScorer, _INVEST_HIGH_THRESHOLD_M
        scorer = InvestSignalScorer()
        pf, pt = _make_period()

        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {"items": [{"tech_id": "TECH_002"}]}

        detail_resp = MagicMock()
        detail_resp.status_code = 200
        detail_resp.json.return_value = {
            "funding": [{"total_amount_million_usd": _INVEST_HIGH_THRESHOLD_M * 2}]
        }

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=search_resp)
            mock_client.get = AsyncMock(return_value=detail_resp)
            mock_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子", domain=None, period_from=pf, period_to=pt)
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_score_no_funding(self):
        from metaprofile.scan_monitor.services.signal_invest import InvestSignalScorer
        scorer = InvestSignalScorer()
        pf, pt = _make_period()

        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.json.return_value = {"items": [{"tech_id": "TECH_003"}]}

        detail_resp = MagicMock()
        detail_resp.status_code = 200
        detail_resp.json.return_value = {"funding": []}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=search_resp)
            mock_client.get = AsyncMock(return_value=detail_resp)
            mock_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子", domain=None, period_from=pf, period_to=pt)
        assert result == 0.0


# ─── PolicySignalScorer ───────────────────────────────────────────────────────

class TestPolicySignalScorer:
    @pytest.mark.asyncio
    async def test_score_returns_zero_on_empty(self):
        from metaprofile.scan_monitor.services.signal_policy import PolicySignalScorer
        scorer = PolicySignalScorer()
        pf, pt = _make_period()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": [], "total": 0}
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子", domain=None, period_from=pf, period_to=pt)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_score_capped_at_one(self):
        from metaprofile.scan_monitor.services.signal_policy import PolicySignalScorer
        scorer = PolicySignalScorer()
        pf, pt = _make_period()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": [{"x": 1}], "total": 200}
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            result = await scorer.score(tech_name="量子", domain="信息技术", period_from=pf, period_to=pt)
        assert result == 1.0


# ─── TRLAnnotator ────────────────────────────────────────────────────────────

class TestTRLAnnotator:
    @pytest.mark.asyncio
    async def test_annotate_returns_trl_annotation(self):
        mock_gateway = MagicMock()
        annotator = TRLAnnotator(mock_gateway)
        expected = TRLAnnotation(trl_level=5, rationale="实验室验证完成", confidence=0.85)
        with patch(
            "metaprofile.scan_monitor.services.trl_annotator.call_with_schema",
            new_callable=AsyncMock,
            return_value=(expected, {}),
        ):
            result = await annotator.annotate(
                tech_name="量子计算",
                tech_summary="量子计算利用量子叠加态",
                current_status="融合分=0.75",
            )
        assert isinstance(result, TRLAnnotation)
        assert 1 <= result.trl_level <= 9
        assert 0.0 <= result.confidence <= 1.0

    def test_trl_annotation_level_bounds(self):
        ann = TRLAnnotation(trl_level=1, rationale="基础原理", confidence=0.5)
        assert ann.trl_level == 1
        with pytest.raises(Exception):
            TRLAnnotation(trl_level=0, rationale="x", confidence=0.5)
        with pytest.raises(Exception):
            TRLAnnotation(trl_level=10, rationale="x", confidence=0.5)


# ─── FrontierAgentValidator ───────────────────────────────────────────────────

class TestFrontierAgentValidator:
    @pytest.mark.asyncio
    async def test_validate_returns_verdict(self):
        mock_gateway = MagicMock()
        validator = FrontierAgentValidator(mock_gateway)
        expected = FrontierAgentVerdict(
            realness=True,
            timeliness=True,
            breakthrough=True,
            final_decision="是",
            evidence="三项均满足",
            confidence=0.90,
        )
        with patch(
            "metaprofile.scan_monitor.services.llm_agent_validator.call_with_schema",
            new_callable=AsyncMock,
            return_value=(expected, {}),
        ):
            result = await validator.validate(
                tech_name="量子计算",
                evidence_pack="五维信号：突现=0.8 专利=0.7 引用=0.6 投资=0.9 政策=0.5",
            )
        assert result.final_decision in ("是", "否", "待定")
        assert 0.0 <= result.confidence <= 1.0

    def test_verdict_final_decision_field(self):
        v = FrontierAgentVerdict(
            realness=False, timeliness=False, breakthrough=False,
            final_decision="否", evidence="缺乏证据", confidence=0.2,
        )
        assert v.final_decision == "否"
