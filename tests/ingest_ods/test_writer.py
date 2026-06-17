from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.ingest_ods.services.writer import Writer


@pytest.mark.asyncio
async def test_write_profile_creates_new_org() -> None:
    session = AsyncMock()
    # 不存在现有 → create
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    w = Writer()
    pid = await w.write_profile(
        session,
        profile_type="org",
        entity_id="ORG_1",
        attrs={"name_cn": "甲", "name_en": "A", "summary": "s", "country": "CN",
               "org_types": [], "nature": "企业", "function": "f", "tech_domains": []},
        scores={"veracity_score": 0.8, "timeliness_score": 0.5, "data_as_of": None},
        method="llm_extract",
    )
    assert pid == "ORG_1"
    assert session.add.call_count >= 2  # ORM + changelog
    await session.flush()


@pytest.mark.asyncio
async def test_write_relations_delegates_to_triple_writer() -> None:
    tw = AsyncMock()
    w = Writer(triple_writer=tw)
    await w.write_relations([{"relation": "PERSON_AFFILIATED_ORG"}])
    tw.write_batch.assert_awaited_once()
