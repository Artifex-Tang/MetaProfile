"""单元测试：shared/enrich/orm_enricher —— 直写 typed ORM 的 LLM 补全核心。"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.foundation.enrichment.llm_filler import FillResult
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.shared.enrich.orm_enricher import enrich_one
from metaprofile.shared.schemas.base import EntityType


def _low_completeness_tech_orm() -> MagicMock:
    """构造一个完整度不足的技术 ORM（缺 tech_summary/current_status/trend 等必填）。"""
    orm = MagicMock(spec=TechProfileORM)
    orm.tech_id = "TECH_1"
    # 必填：3 个有值，3 个缺失
    orm.tech_name_cn = "量子计算"
    orm.tech_name_en = "Quantum Computing"
    orm.tech_domain = ["信息技术"]
    orm.tech_summary = None        # 缺失
    orm.current_status = None      # 缺失
    orm.trend = None               # 缺失
    # 推荐：全缺
    orm.dev_goal = None
    orm.key_points = []
    orm.autonomy_capability = None
    orm.tech_advantages = None
    orm.invention_date = None
    orm.completeness = 0.2
    orm.data_as_of = None
    return orm


@pytest.mark.asyncio
async def test_enrich_one_fills_missing_and_updates_completeness():
    orm = _low_completeness_tech_orm()
    session = AsyncMock()
    session.add = MagicMock()  # session.add 同步；AsyncMock 默认异步会留 coroutine 警告
    session.get = AsyncMock(return_value=orm)

    filler = MagicMock()
    filler.fill = AsyncMock(return_value=FillResult(
        filled_fields={"tech_summary": "量子计算利用量子力学原理。", "current_status": "实验室阶段"},
        confidence=0.9,
        accepted_fields=["tech_summary", "current_status"],
        rejected_fields=[],
    ))

    result = await enrich_one(
        session=session,
        entity_type=EntityType.TECH,
        orm_cls=TechProfileORM,
        entity_id="TECH_1",
        filler=filler,
        change_log_entity_type="tech",
    )

    assert result.error is None
    assert result.skipped is False
    assert result.completeness_after > result.completeness_before
    assert set(result.filled_fields) == {"tech_summary", "current_status"}
    # ORM 直写
    assert orm.tech_summary == "量子计算利用量子力学原理。"
    assert orm.current_status == "实验室阶段"
    assert orm.data_as_of == date.today()
    assert orm.completeness == result.completeness_after
    # ChangeLog + commit
    assert session.add.called
    added = session.add.call_args[0][0]
    assert added.method == "llm_enrich"
    assert added.entity_type == "tech"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrich_one_returns_not_found_when_missing():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    filler = MagicMock()

    result = await enrich_one(
        session=session,
        entity_type=EntityType.TECH,
        orm_cls=TechProfileORM,
        entity_id="NOPE",
        filler=filler,
        change_log_entity_type="tech",
    )
    assert result.error == "entity_not_found"
    filler.fill.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_one_skips_when_completeness_sufficient():
    orm = MagicMock(spec=TechProfileORM)
    orm.tech_id = "TECH_FULL"
    # 所有 TECH 必填+推荐都有值 → 高完整度
    for f in ["tech_name_cn", "tech_name_en", "tech_domain", "tech_summary",
              "current_status", "trend", "dev_goal", "key_points",
              "autonomy_capability", "tech_advantages", "invention_date"]:
        setattr(orm, f, "x" if f != "tech_domain" and f != "key_points" else ["x"])
    orm.completeness = 0.95

    session = AsyncMock()
    session.get = AsyncMock(return_value=orm)
    filler = MagicMock()
    filler.fill = AsyncMock()

    result = await enrich_one(
        session=session,
        entity_type=EntityType.TECH,
        orm_cls=TechProfileORM,
        entity_id="TECH_FULL",
        filler=filler,
        change_log_entity_type="tech",
    )
    assert result.skipped is True
    filler.fill.assert_not_called()
    session.commit.assert_not_awaited()
