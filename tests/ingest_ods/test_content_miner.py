from unittest.mock import AsyncMock

import pytest

from metaprofile.ingest_ods.services.content_miner import ContentMiner


class _Resp:
    def __init__(self, c: str) -> None:
        self.content = c


LLM_JSON = ('{"entities":[{"type":"org","name":"甲公司","attrs":{"summary":"研发AI"},'
            '"veracity_hint":0.9,"as_of":"2026-01-01"}],'
            '"relations":[{"subject_name":"甲公司","subject_type":"org",'
            '"object_name":"深度学习","object_type":"tech","predicate":"涉及",'
            '"evidence":"甲公司研发深度学习","confidence":0.8}]}')


@pytest.mark.asyncio
async def test_mine_parses_entities_and_relations() -> None:
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=_Resp(LLM_JSON))
    cm = ContentMiner(llm=llm)
    entities, relations = await cm.mine(
        attachments=[{"original_id": 15, "clean_content": "正文……"}],
    )
    assert len(entities) == 1
    assert entities[0]["name"] == "甲公司"
    assert len(relations) == 1
    assert relations[0].relation.value == "涉及"
    assert relations[0].subject_id  # 已赋临时 id


@pytest.mark.asyncio
async def test_mine_skips_null_clean_content() -> None:
    llm = AsyncMock()
    cm = ContentMiner(llm=llm)
    entities, relations = await cm.mine([{"original_id": 1, "clean_content": None}])
    assert entities == [] and relations == []
    llm.complete.assert_not_awaited()
