from unittest.mock import AsyncMock

import pytest

from metaprofile.ingest_ods.services.resolver import EntityResolver


def _row(ptype, key, attrs):
    return {"profile_type": ptype, "entity_key": key,
            "raw_payload": {"_attrs": attrs}, "source_id": "1"}


@pytest.mark.asyncio
async def test_merge_on_strong_key() -> None:
    rows = [
        _row("org", {"company_id": 1, "usc_code": "U1"}, {"name_cn": "甲", "summary": "a"}),
        _row("org", {"company_id": 1, "usc_code": "U1"}, {"founded_date": "2010-01-01"}),
    ]
    res = EntityResolver(llm=AsyncMock())
    entities = await res.resolve(rows)
    assert len(entities) == 1
    assert entities[0]["attrs"]["name_cn"] == "甲"
    assert entities[0]["attrs"]["founded_date"] == "2010-01-01"


@pytest.mark.asyncio
async def test_weak_key_disambig_same() -> None:
    rows = [
        _row("person", {"full_name_employer": "李四|上海交大"}, {"name_cn": "李四"}),
        _row("person", {}, {"name_cn": "李四", "current_org": "上海交大"}),  # 无强键
    ]
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=_Resp('{"same": true, "reason": "x"}'))
    res = EntityResolver(llm=llm)
    entities = await res.resolve(rows)
    assert len(entities) == 1


class _Resp:
    def __init__(self, content: str) -> None:
        self.content = content


@pytest.mark.asyncio
async def test_weak_key_disambig_different() -> None:
    """LLM says NOT same → 2 distinct entities."""
    rows = [
        _row("person", {"full_name_employer": "李四|上海交大"}, {"name_cn": "李四"}),
        _row("person", {}, {"name_cn": "李四", "current_org": "清华大学"}),
    ]
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=_Resp('{"same": false, "reason": "不同人"}'))
    res = EntityResolver(llm=llm)
    entities = await res.resolve(rows)
    assert len(entities) == 2


@pytest.mark.asyncio
async def test_empty_name_cluster_passes_through_unmerged() -> None:
    """Weak row with no usable name → not clustered/merged, emitted as-is."""
    rows = [
        _row("person", {}, {"current_org": "某机构"}),  # name_cn absent
    ]
    res = EntityResolver(llm=AsyncMock())
    entities = await res.resolve(rows)
    assert len(entities) == 1
