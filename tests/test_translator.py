from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.shared.enrich.translator import NAME_FIELDS, TranslateOutcome, translate_name_one


def test_name_fields_covers_four_types():
    assert NAME_FIELDS["tech"] == ("tech_name_cn", "tech_name_en")
    assert NAME_FIELDS["org"] == ("name_cn", "name_en")
    assert NAME_FIELDS["person"] == ("name_cn", "name_en")
    assert NAME_FIELDS["project"] == ("name_cn", "name_en")


@pytest.mark.asyncio
async def test_translate_skips_when_name_cn_present():
    orm = MagicMock(); orm.tech_name_cn = "量子计算"; orm.tech_name_en = "quantum"
    session = AsyncMock(); session.get = AsyncMock(return_value=orm)
    gateway = MagicMock(); gateway.complete = AsyncMock()
    out = await translate_name_one(session, "tech", "T1", gateway=gateway)
    assert isinstance(out, TranslateOutcome)
    assert out.translated is False and out.reason == "name_cn_present"
    gateway.complete.assert_not_called()


@pytest.mark.asyncio
async def test_translate_skips_when_no_name_en():
    orm = MagicMock(); orm.tech_name_cn = ""; orm.tech_name_en = ""
    session = AsyncMock(); session.get = AsyncMock(return_value=orm)
    gateway = MagicMock(); gateway.complete = AsyncMock()
    out = await translate_name_one(session, "tech", "T1", gateway=gateway)
    assert out.translated is False and out.reason == "no_source"
    gateway.complete.assert_not_called()


@pytest.mark.asyncio
async def test_translate_writes_name_cn_and_changelog():
    orm = MagicMock(); orm.tech_name_cn = ""; orm.tech_name_en = "quantum computing"
    session = AsyncMock(); session.get = AsyncMock(return_value=orm)
    resp = MagicMock(); resp.content = "量子计算"
    gateway = MagicMock(); gateway.complete = AsyncMock(return_value=resp)
    out = await translate_name_one(session, "tech", "T1", gateway=gateway)
    assert out.translated is True and out.new_value == "量子计算"
    assert orm.tech_name_cn == "量子计算"
    session.add.assert_called()  # EntityChangeLogORM


@pytest.mark.asyncio
async def test_translate_failed_keeps_name_cn_empty():
    orm = MagicMock(); orm.tech_name_cn = ""; orm.tech_name_en = "quantum"
    session = AsyncMock(); session.get = AsyncMock(return_value=orm)
    gateway = MagicMock(); gateway.complete = AsyncMock(side_effect=Exception("llm down"))
    out = await translate_name_one(session, "tech", "T1", gateway=gateway)
    assert out.translated is False and out.error
    assert orm.tech_name_cn == ""  # 失败不污染


@pytest.mark.asyncio
async def test_translate_project_wraps_list():
    orm = MagicMock(); orm.name_cn = []; orm.name_en = ["quantum"]
    session = AsyncMock(); session.get = AsyncMock(return_value=orm)
    resp = MagicMock(); resp.content = "量子"
    gateway = MagicMock(); gateway.complete = AsyncMock(return_value=resp)
    out = await translate_name_one(session, "project", "P1", gateway=gateway)
    assert out.translated is True
    assert orm.name_cn == ["量子"]  # project name_cn 是 list
