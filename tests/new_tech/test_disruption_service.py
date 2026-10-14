"""Phase C:DisruptionService 组件构建 + Rotolo 中位判定。"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.new_tech_discovery.services.disruption_metrics import z_scores
from metaprofile.new_tech_discovery.services.disruption_service import (
    build_components,
)
from metaprofile.new_tech_discovery.services.rotolo_validator import (
    RotoloScores,
    median_verdict,
)


def _rows():
    # 2024: G06T 常规对(旧); G06N 新颖域(单人申请人, 新词)
    return [
        (2024, "A;B", "G06T7/73;G06F1/00", "常规标题词汇"),
        (2024, "A", "G06N3/08;H04L9/32", "old words here"),
        (2025, "A", "G06T7/73;G06F1/00", "常规标题词汇"),
        (2025, "A", "G06N3/08;H05H1/00", "neuro symbolic fabric"),   # 新对+新词+单人
        (2025, "A;B", "G06N3/08;H05H1/00", "neuro fabric chip"),
    ]


def test_build_components_produces_all_dims():
    rows = build_components(_rows())
    ids = {r["object_id"] for r in rows}
    assert {"ipc:G06T", "ipc:G06N"} <= ids
    g06n = next(r for r in rows if r["object_id"] == "ipc:G06N")
    assert g06n["window_month"] == date(2025, 1, 1)
    for dim in ("novelty_comb", "growth", "new_entrant", "small_team", "term_novelty"):
        assert dim in g06n and isinstance(g06n[dim], float)
    assert "disrupt_score" in g06n
    assert "raw" in g06n


def test_novelty_prefers_new_pair_domain():
    rows = build_components(_rows())
    g06t = next(r for r in rows if r["object_id"] == "ipc:G06T")
    g06n = next(r for r in rows if r["object_id"] == "ipc:G06N")
    # G06N 2025 全部含历史未见对(H05H) → 原始新颖度 1.0;G06T 对全旧 → 0.0
    assert g06n["raw"]["novelty_comb"] == 1.0
    assert g06t["raw"]["novelty_comb"] == 0.0


def test_median_verdict_thresholds():
    def s(n, g, i, c, a):
        return RotoloScores(novelty=n, growth=g, impact=i, coherence=c,
                            ambiguity=a, rationale="r", confidence=0.9)

    scores, comp, verdict, _ = median_verdict([s(5, 5, 4, 4, 4)] * 3)
    assert verdict == "是" and comp >= 4.0
    _, _, verdict2, _ = median_verdict([s(1, 2, 2, 1, 2)] * 3)
    assert verdict2 == "否"
    _, _, verdict3, _ = median_verdict([s(3, 3, 3, 3, 3)] * 3)
    assert verdict3 == "待定"
    assert median_verdict([])[2] == "pending"


@pytest.mark.asyncio
async def test_compute_no_db_connection():
    from metaprofile.new_tech_discovery.services.disruption_service import (
        DisruptionService,
    )

    fake_sess = MagicMock()
    fake_sess.get = AsyncMock(return_value=None)
    svc = DisruptionService(db_connection_id=999)
    with patch("metaprofile.new_tech_discovery.services.disruption_service.get_session") as gs:
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=fake_sess)
        ctx.__aexit__ = AsyncMock(return_value=False)
        gs.return_value = ctx
        res = await svc.compute(llm=False)
    assert res["status"] == "failed"


def test_z_scores_guard():
    assert z_scores({}) == {}
