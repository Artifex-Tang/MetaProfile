"""Phase A4:EntityLinker 把语料实体串链到画像表(org/person/tech)。

select(id_col).scalars() 返回 id 值列表(非行对象),fake 直接给 id 串。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.new_tech_discovery.services.entity_linker import EntityLinker


def _fake_db_with_rows(ids):
    """db.execute → result.scalars().all() == ids 的 async mock。"""
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = ids
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_link_orgs_exact_name_hits():
    db = _fake_db_with_rows(["ORG-1"])
    ids = await EntityLinker(db).link_orgs(["ACME 公司", "未知机构"])
    assert ids == ["ORG-1"]


@pytest.mark.asyncio
async def test_link_orgs_dedup_and_cap():
    db = _fake_db_with_rows(["ORG-1", "ORG-2", "ORG-3"])
    ids = await EntityLinker(db).link_orgs(["机构A", "机构B", "机构C", "机构A"], cap=2)
    assert len(ids) == 2


@pytest.mark.asyncio
async def test_link_persons_empty_names_no_query():
    db = _fake_db_with_rows([])
    ids = await EntityLinker(db).link_persons(["", "  "])
    assert ids == []
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_link_techs_by_name():
    db = _fake_db_with_rows(["concept:abc"])
    ids = await EntityLinker(db).link_techs(["量子计算"])
    assert ids == ["concept:abc"]


@pytest.mark.asyncio
async def test_link_orgs_skips_query_when_all_names_filtered():
    """超短/空名过滤后无候选 → 不打 DB。"""
    db = _fake_db_with_rows([])
    await EntityLinker(db).link_orgs(["x"])  # len<2 过滤
    db.execute.assert_not_awaited()
