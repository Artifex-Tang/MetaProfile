"""Phase B5:EmergenceService 域/对行构建 + upsert(纯构建部分,无真 DB)。"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.new_tech_discovery.services.emergence_service import (
    EmergenceService,
    build_domain_rows,
    build_pair_rows,
    persist_indicators,
    subclasses_of,
)


def test_subclasses_of_multi_ipc():
    assert subclasses_of("G06T7/73(2017.01)I") == ["G06T"]
    assert subclasses_of("G06N3/08;G06T7/73, H04N1/00") == ["G06N", "G06T", "H04N"]
    assert subclasses_of("") == []
    assert subclasses_of(None) == []


def _patent_rows():
    # 2024: G06T×3(申请人 A,B / B,C / A,C), G06N×2; 2025: G06T×5
    return [
        (2024, "A;B", "G06T7/73(2017.01)I"),
        (2024, "B;C", "G06T7/00(2017.01)I"),
        (2024, "A;C", "G06N3/08;G06T7/73"),
        (2024, "D", "G06N3/08(2017.01)I"),
        (2025, "A;E", "G06T7/73(2017.01)I"),
        (2025, "B", "G06T7/00(2017.01)I"),
        (2025, "F", "G06T7/60(2017.01)I"),
        (2025, "A", "G06T2207/81"),
        (2025, "G", "G06T2207/20"),
    ]


def test_build_domain_rows_metrics():
    rows = build_domain_rows(_patent_rows())
    g06t = next(r for r in rows if r["object_id"] == "ipc:G06T")
    assert g06t["object_type"] == "ipc_domain"
    assert g06t["window_month"] == date(2025, 1, 1)
    m = g06t["metrics"]
    assert m["patents"] == 5                     # 2025 G06T(含多 IPC 专利)
    assert m["applicants"] == 5                  # 去重 {A,E,B,F,G}
    assert m["tem_quadrant"] in {"weak", "strong", "latent", "nswb"}
    assert m["s_curve_stage"] in {
        "emerging", "growth", "mature", "saturated", "insufficient",
    }
    assert m["new_entrant_ratio"] >= 0.0


def test_build_pair_rows_new_pair_detected():
    rows = build_pair_rows(_patent_rows(), lookback_years=3, min_salton=0.05)
    pair_ids = [r["object_id"] for r in rows]
    assert "G06N|G06T" in pair_ids                 # 2024 共类对,首现近 → 新对
    p = next(r for r in rows if r["object_id"] == "G06N|G06T")
    assert p["metrics"]["first_seen"] == 2024
    assert p["object_type"] == "ipc_pair"


def test_persist_indicators_upsert_called_per_chunk():
    db = MagicMock()
    db.execute = AsyncMock()
    rows = [
        {"object_type": "ipc_domain", "object_id": f"ipc:X{i}",
         "window_month": date(2025, 1, 1), "metrics": {}}
        for i in range(3)
    ]
    import asyncio
    n = asyncio.run(persist_indicators(db, rows))
    assert n == 3
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_compute_no_db_connection():
    fake_sess = MagicMock()
    fake_sess.get = AsyncMock(return_value=None)
    svc = EmergenceService(db_connection_id=999)
    with patch("metaprofile.new_tech_discovery.services.emergence_service.get_session") as gs:
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=fake_sess)
        ctx.__aexit__ = AsyncMock(return_value=False)
        gs.return_value = ctx
        res = await svc.compute()
    assert res["status"] == "failed"
