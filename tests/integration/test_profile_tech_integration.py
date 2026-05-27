"""集成测试：profile_tech 服务层（需真实 PostgreSQL）。"""
from __future__ import annotations

from datetime import date

import pytest

from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.profile_tech.schemas.request import SearchRequest, UpdateTechProfileRequest
from metaprofile.profile_tech.services.tech_profile_service import TechProfileService
from metaprofile.profile_tech.services.tech_query_service import TechQueryService
from metaprofile.profile_tech.services.tech_stats_service import TechStatsService
from metaprofile.shared.schemas.entity_tech import TechProfile

pytestmark = pytest.mark.asyncio


def _make_orm(tech_id: str = "TECH_20260527_int0001") -> TechProfileORM:
    return TechProfileORM(
        tech_id=tech_id,
        tech_name_cn="量子计算",
        tech_name_en="Quantum Computing",
        tech_domain=["信息技术", "量子物理"],
        tech_summary="量子计算利用量子力学原理进行信息处理。",
        current_status="实验室验证阶段",
        trend="上升",
        project_layout=[],
        key_points=[],
        confidence=0.9,
        completeness=0.85,
    )


# ── TechQueryService ──────────────────────────────────────────────────────────

async def test_get_tech_profile_found(db_session):
    orm = _make_orm()
    db_session.add(orm)
    await db_session.flush()

    svc = TechQueryService()
    result = await svc.get_by_id(db_session, "TECH_20260527_int0001")
    assert result is not None
    assert result.tech_id == "TECH_20260527_int0001"
    assert result.tech_name_cn == "量子计算"


async def test_get_tech_profile_not_found(db_session):
    svc = TechQueryService()
    result = await svc.get_by_id(db_session, "TECH_NONEXISTENT_99")
    assert result is None


async def test_search_tech_by_keyword(db_session):
    orm = _make_orm("TECH_20260527_int0002")
    db_session.add(orm)
    await db_session.flush()

    svc = TechQueryService()
    req = SearchRequest(keyword="量子", page=1, page_size=10)
    result = await svc.search(db_session, req)
    assert result.total >= 1
    assert any(item.tech_id == "TECH_20260527_int0002" for item in result.items)


async def test_search_tech_no_match(db_session):
    svc = TechQueryService()
    req = SearchRequest(keyword="XYZNOTEXIST99999", page=1, page_size=10)
    result = await svc.search(db_session, req)
    assert result.total == 0
    assert result.items == []


# ── TechProfileService ────────────────────────────────────────────────────────

async def test_create_tech_profile(db_session):
    svc = TechProfileService()
    profile = TechProfile(
        tech_name_cn="人工智能",
        tech_name_en="Artificial Intelligence",
        tech_domain=["信息技术"],
        tech_summary="AI 利用机器学习模拟人类智能。",
        current_status="广泛应用",
        trend="持续增长",
        project_layout=[],
        key_points=[],
    )
    result = await svc.create(db_session, profile=profile)
    assert result.tech_id.startswith("TECH_")
    assert result.tech_name_cn == "人工智能"


async def test_update_tech_profile(db_session):
    orm = _make_orm("TECH_20260527_int0003")
    db_session.add(orm)
    await db_session.flush()

    svc = TechProfileService()
    req = UpdateTechProfileRequest(
        tech_summary="更新后的技术概述",
        operator="alice",
    )
    result = await svc.update(db_session, tech_id="TECH_20260527_int0003", payload=req)
    assert result is not None
    assert result.tech_summary == "更新后的技术概述"


async def test_update_tech_profile_not_found(db_session):
    svc = TechProfileService()
    req = UpdateTechProfileRequest(tech_summary="x", operator="alice")
    result = await svc.update(db_session, tech_id="TECH_NONEXISTENT_99", payload=req)
    assert result is None


# ── TechStatsService ──────────────────────────────────────────────────────────

async def test_compute_stats_returns_response(db_session):
    orm = _make_orm("TECH_20260527_int0004")
    db_session.add(orm)
    await db_session.flush()

    svc = TechStatsService()
    stats = await svc.compute(db_session)
    assert stats.total >= 1


async def test_compute_stats_empty_db(db_session):
    svc = TechStatsService()
    stats = await svc.compute(db_session)
    assert stats.total >= 0
