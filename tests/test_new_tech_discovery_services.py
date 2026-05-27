"""单元测试：new_tech_discovery 服务（anomaly, trend, adaptive_threshold, network）。"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.new_tech_discovery.services.weak_signal_extractor import SignalStrengthQuantifier


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_period() -> tuple[date, date]:
    return date(2026, 1, 1), date(2026, 1, 31)


# ─── SignalStrengthQuantifier ─────────────────────────────────────────────────

class TestSignalStrengthQuantifier:
    def _q(self) -> SignalStrengthQuantifier:
        return SignalStrengthQuantifier()

    def test_quantify_all_max(self):
        q = self._q()
        result = q.quantify(novelty=1.0, coherence=1.0, diversity=1.0, velocity=1.0)
        assert abs(result - 1.0) < 1e-6

    def test_quantify_all_zero(self):
        q = self._q()
        result = q.quantify(novelty=0.0, coherence=0.0, diversity=0.0, velocity=0.0)
        assert result == 0.0

    def test_quantify_weights_sum_to_one(self):
        # 0.30 + 0.25 + 0.20 + 0.25 = 1.0
        assert abs(0.30 + 0.25 + 0.20 + 0.25 - 1.0) < 1e-9

    def test_quantify_partial(self):
        q = self._q()
        result = q.quantify(novelty=1.0, coherence=0.0, diversity=0.0, velocity=0.0)
        assert abs(result - 0.30) < 1e-6


# ─── AnomalyDetector ─────────────────────────────────────────────────────────

class TestAnomalyDetector:
    @pytest.mark.asyncio
    async def test_detect_empty_on_http_error(self):
        from metaprofile.new_tech_discovery.services.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()
        pf, pt = _make_period()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            results = await detector.detect(domain=None, period_from=pf, period_to=pt)
        assert results == []

    @pytest.mark.asyncio
    async def test_detect_exception_returns_empty(self):
        from metaprofile.new_tech_discovery.services.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()
        pf, pt = _make_period()
        with patch("httpx.AsyncClient", side_effect=Exception("timeout")):
            results = await detector.detect(domain=None, period_from=pf, period_to=pt)
        assert results == []

    def test_ensemble_detect_empty_input(self):
        from metaprofile.new_tech_discovery.services.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()
        results = detector._ensemble_detect([])
        assert results == []

    def test_ensemble_detect_high_anomaly(self):
        from metaprofile.new_tech_discovery.services.anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()
        features = [
            {"tech_id": "T1", "tech_name": "量子计算", "funding": 200.0, "citations": 500, "completeness": 0.9},
            {"tech_id": "T2", "tech_name": "人工智能", "funding": 10.0, "citations": 20, "completeness": 0.5},
        ]
        results = detector._ensemble_detect(features)
        # T1 should be detected as anomaly (highest funding + citations)
        assert len(results) >= 1
        assert results[0].tech_id == "T1"


# ─── TrendRecognizer ─────────────────────────────────────────────────────────

class TestTrendRecognizer:
    @pytest.mark.asyncio
    async def test_recognize_returns_empty_on_short_series(self):
        from metaprofile.new_tech_discovery.services.trend_recognizer import TrendRecognizer
        recognizer = TrendRecognizer()
        # period of 1 day → only 1 window → len(series) < 4
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"total": 5}
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_client
            results = await recognizer.recognize(
                domain=None,
                period_from=date(2026, 1, 1),
                period_to=date(2026, 1, 2),
                window_days=7,
            )
        assert results == []

    def test_mann_kendall_rising_series(self):
        from metaprofile.new_tech_discovery.services.trend_recognizer import TrendRecognizer
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        score, slope = TrendRecognizer._mann_kendall(series)
        assert score > 0.5
        assert slope > 0

    def test_mann_kendall_falling_series(self):
        from metaprofile.new_tech_discovery.services.trend_recognizer import TrendRecognizer
        series = [5.0, 4.0, 3.0, 2.0, 1.0]
        score, _ = TrendRecognizer._mann_kendall(series)
        assert score < 0.5

    def test_mann_kendall_flat_series(self):
        from metaprofile.new_tech_discovery.services.trend_recognizer import TrendRecognizer
        series = [3.0, 3.0, 3.0, 3.0]
        score, slope = TrendRecognizer._mann_kendall(series)
        assert abs(score - 0.5) < 1e-6
        assert slope == 0.0


# ─── AdaptiveThreshold ───────────────────────────────────────────────────────

class TestAdaptiveThreshold:
    @pytest.mark.asyncio
    async def test_compute_returns_default_on_db_error(self):
        from metaprofile.new_tech_discovery.services.adaptive_threshold import AdaptiveThreshold, _DEFAULT_THRESHOLD
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB unavailable")
        threshold = AdaptiveThreshold(mock_db)
        result = await threshold.compute()
        assert result == _DEFAULT_THRESHOLD

    @pytest.mark.asyncio
    async def test_compute_clamped_to_range(self):
        from metaprofile.new_tech_discovery.services.adaptive_threshold import AdaptiveThreshold
        mock_db = AsyncMock()
        mock_row = MagicMock()
        mock_row.mean = 0.95
        mock_row.std = 0.5
        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_db.execute = AsyncMock(return_value=mock_result)
        threshold = AdaptiveThreshold(mock_db)
        result = await threshold.compute()
        assert result <= 1.0

    def test_is_above(self):
        from metaprofile.new_tech_discovery.services.adaptive_threshold import AdaptiveThreshold
        assert AdaptiveThreshold.is_above(0.7, 0.5) is True
        assert AdaptiveThreshold.is_above(0.3, 0.5) is False
        assert AdaptiveThreshold.is_above(0.5, 0.5) is True


# ─── NetworkCorrelator ────────────────────────────────────────────────────────

class TestNetworkCorrelator:
    @pytest.mark.asyncio
    async def test_build_network_with_related_ids(self):
        from metaprofile.new_tech_discovery.services.network_correlator import NetworkCorrelator
        from metaprofile.new_tech_discovery.domain.orm_models import WeakSignalORM

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        signal = MagicMock(spec=WeakSignalORM)
        signal.signal_id = "SIG_001"
        signal.domain = "信息技术"
        signal.related_tech_ids = ["TECH_001"]
        signal.related_org_ids = ["ORG_001"]
        signal.related_person_ids = ["PERSON_001"]

        pf, pt = _make_period()
        fetch_mock = AsyncMock(return_value=[])
        correlator = NetworkCorrelator(mock_db)
        with patch.object(correlator, "_fetch_related_techs", fetch_mock):
            edges = await correlator.build_network(signal=signal, period_from=pf, period_to=pt)

        # Expect edges for tech + org + person
        assert len(edges) == 3

    @pytest.mark.asyncio
    async def test_fetch_related_techs_returns_empty_on_error(self):
        from metaprofile.new_tech_discovery.services.network_correlator import NetworkCorrelator
        mock_db = AsyncMock()
        correlator = NetworkCorrelator(mock_db)
        pf, pt = _make_period()
        with patch("httpx.AsyncClient", side_effect=Exception("timeout")):
            result = await correlator._fetch_related_techs("信息技术", pf, pt)
        assert result == []
