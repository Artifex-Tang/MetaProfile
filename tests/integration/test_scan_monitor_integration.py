"""集成测试：scan_monitor 域模型持久化（需真实 PostgreSQL）。"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from metaprofile.scan_monitor.domain.orm_models import FrontierTechORM, ScanAlertORM
from metaprofile.scan_monitor.services.fusion_scorer import FrontierTechFusionScorer

pytestmark = pytest.mark.asyncio


def _make_frontier(task_id: str = "scan-task-001", fusion_score: float = 0.75) -> FrontierTechORM:
    return FrontierTechORM(
        scan_task_id=task_id,
        tech_name="量子计算",
        tech_domain=["信息技术"],
        period_from=date(2026, 1, 1),
        period_to=date(2026, 1, 31),
        burst_score=0.8,
        patent_score=0.7,
        citation_score=0.6,
        invest_score=0.9,
        policy_score=0.5,
        fusion_score=fusion_score,
        llm_validated=True,
        llm_verdict="是",
        trl_level=5,
        status="validated",
    )


async def test_create_frontier_tech(db_session):
    orm = _make_frontier()
    db_session.add(orm)
    await db_session.flush()
    assert orm.id is not None
    assert orm.tech_name == "量子计算"


async def test_frontier_tech_fusion_score_persisted(db_session):
    orm = _make_frontier(fusion_score=0.82)
    db_session.add(orm)
    await db_session.flush()
    assert abs(orm.fusion_score - 0.82) < 1e-4


async def test_scan_alert_created(db_session):
    alert = ScanAlertORM(
        tech_name="量子通信",
        alert_type="burst",
        severity="warn",
        message="专利异动超基线 2.5 倍",
        fired_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.flush()
    assert alert.id is not None
    assert alert.severity == "warn"


async def test_multiple_frontier_records_ordered(db_session):
    for i, score in enumerate([0.9, 0.7, 0.5]):
        db_session.add(_make_frontier(task_id=f"scan-order-{i}", fusion_score=score))
    await db_session.flush()

    from sqlalchemy import desc, select
    from metaprofile.scan_monitor.domain.orm_models import FrontierTechORM as ORM
    rows = (await db_session.execute(
        select(ORM).where(ORM.scan_task_id.like("scan-order-%"))
        .order_by(desc(ORM.fusion_score))
    )).scalars().all()
    assert rows[0].fusion_score >= rows[-1].fusion_score


async def test_fusion_scorer_deterministic():
    scorer = FrontierTechFusionScorer()
    s1 = scorer.fuse(burst=0.8, patent=0.7, citation=0.6, invest=0.9, policy=0.5)
    s2 = scorer.fuse(burst=0.8, patent=0.7, citation=0.6, invest=0.9, policy=0.5)
    assert s1 == s2
    assert 0.0 <= s1 <= 1.0
