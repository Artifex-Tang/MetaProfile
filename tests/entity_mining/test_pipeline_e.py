"""Phase E 测试:fusion 混合 / frontier 候选(mock db) / cron registry / 演进链。"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.scan_monitor.services.frontier_candidate_service import blend_fusion


def test_blend_fusion_weights_and_clamp():
    assert blend_fusion(1.0, 1.0, 1.0) == 1.0
    assert blend_fusion(0.5, 0.0, 0.0) == 0.25     # 0.5*0.5
    assert blend_fusion(2.0, -1.0, 0.0) == 0.5     # 负/超1 归一


def test_registry_has_intel_task_types():
    from metaprofile.shared.scheduler.poller import _build_registry

    reg = _build_registry()
    assert {"weak_signal_scan", "emergence_scan", "disruption_scan"} <= set(reg)
    assert {"translate_batch", "collection"} <= set(reg)


def test_scheduler_allowlist_accepts_new_types():
    from metaprofile.settings_api.api.routes_scheduler import _ALLOWED_TASK_TYPES

    assert "weak_signal_scan" in _ALLOWED_TASK_TYPES
    assert "emergence_scan" in _ALLOWED_TASK_TYPES


def test_relation_enum_has_cooccurs():
    from metaprofile.shared.schemas.relations import RelationType

    assert RelationType.TECH_CO_OCCURS.value == "共现"


def _mock_db(result_seq):
    """db.execute 依次返回 result(带 scalars().all() / scalar())。"""
    db = MagicMock()
    db.execute = AsyncMock(side_effect=result_seq)
    db.add_all = MagicMock()
    db.flush = AsyncMock()
    return db


def _scalars_result(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    r.scalar.return_value = None
    return r


def _scalar_result(v):
    r = MagicMock()
    r.scalars.return_value.all.return_value = []
    r.scalar.return_value = v
    return r


class _FakeSignal:
    def __init__(self, kw, strength):
        self.signal_id = f"WS-{kw}"
        self.keywords = [kw]
        self.strength = strength
        self.domain = None


class _FakeIndicator:
    def __init__(self, obj, quadrant, growth):
        self.object_id = obj
        self.metrics = {"tem_quadrant": quadrant, "tem_growth": growth}


class _FakeDisruption:
    def __init__(self, obj, score):
        self.object_id = obj
        self.disrupt_score = score


@pytest.mark.asyncio
async def test_build_frontier_candidates_merges_sources():
    from metaprofile.scan_monitor.services.frontier_candidate_service import (
        build_frontier_candidates,
    )

    db = _mock_db([
        _scalar_result(0.8),   # max strength
        _scalar_result(3.0),   # max disrupt
        _scalars_result([_FakeSignal("quantum", 0.8), _FakeSignal("cobots", 0.4)]),
        _scalars_result([
            _FakeIndicator("ipc:G06T", "weak", 0.6),
            _FakeIndicator("ipc:G06F", "mature", 0.9),   # 非 weak/strong 跳过
        ]),
        _scalars_result([_FakeDisruption("ipc:G06T", 3.0)]),  # 与指标同名 → 补 disrupt
    ])
    res = await build_frontier_candidates(
        db, period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )
    assert res["candidates"] == 3      # quantum + cobots + G06T(融合指标与颠覆)
    added_rows = [c.args[0] for c in db.add_all.call_args_list if c.args]
    frontier_rows = [r for batch in added_rows for r in batch
                     if type(r).__name__ == "FrontierTechORM"]
    assert len(frontier_rows) == 3
    g06t = next(r for r in frontier_rows if r.tech_name == "G06T")
    # burst=0 patent=0.6 disrupt=1.0 → 0.3*0.6+0.2*1.0=0.38
    assert g06t.fusion_score == 0.38
    assert g06t.patent_score == 0.6


@pytest.mark.asyncio
async def test_sync_validated_to_topics_creates_pending():
    from metaprofile.scan_monitor.services.frontier_candidate_service import (
        sync_validated_to_topics,
    )

    class _F:
        tech_id = "ipc:G06T"
        tech_name = "G06T"
        llm_evidence = "证据"
        fusion_score = 0.7
        patent_score = 0.5
        period_from = date(2026, 1, 15)

    db = _mock_db([_scalars_result([_F()]), _scalars_result([])])
    db.add = MagicMock()
    n = await sync_validated_to_topics(db)
    assert n == 1
    topic = db.add.call_args[0][0]
    assert topic.status == "pending"
    assert topic.final_score == round(0.6 * 0.7 + 0.4 * 0.5, 4)


def test_author_dedup_threshold_floors_low_pairs():
    from metaprofile.entity_mining.services.author_dedup import (
        build_author_records,
        dedup_pairs,
    )

    rows = [("王芳;李雷", "d1", 2024), ("王芳华;韩梅", "d2", 2024)]
    pairs = dedup_pairs(build_author_records(rows), threshold=0.7)
    # 无共作者、姓名相似一般 → 不产建议
    assert pairs == []
