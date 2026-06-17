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
    entities, relations, unmapped = await cm.mine(
        attachments=[{"original_id": 15, "clean_content": "正文……"}],
    )
    assert len(entities) == 1
    assert entities[0]["name"] == "甲公司"
    assert len(relations) == 1
    assert relations[0].relation.value == "涉及"
    assert relations[0].subject_id  # 已赋临时 id
    assert unmapped == []  # 已映射谓词不进 staging


@pytest.mark.asyncio
async def test_mine_skips_null_clean_content() -> None:
    llm = AsyncMock()
    cm = ContentMiner(llm=llm)
    entities, relations, unmapped = await cm.mine(
        [{"original_id": 1, "clean_content": None}]
    )
    assert entities == [] and relations == [] and unmapped == []
    llm.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_mine_tolerates_extra_keys_in_llm_output() -> None:
    """extra='forbid' + stray LLM key must not crash the batch (regression)."""
    bad_json = ('{"entities":[{"type":"org","name":"X","stray_extra_field":1}],'
                '"relations":[]}')
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=_Resp(bad_json))
    cm = ContentMiner(llm=llm)
    # Must NOT raise; returns 3-tuple — empty is fine.
    entities, relations, unmapped = await cm.mine(
        [{"original_id": 1, "clean_content": "正文"}]
    )
    assert isinstance(entities, list)
    assert isinstance(relations, list)
    assert isinstance(unmapped, list)


@pytest.mark.asyncio
async def test_mine_routes_unmapped_predicate_to_staging_list():
    """未映射谓词不丢弃,进 unmapped 返回列表(供 collector 写 relation_staging)。"""
    llm = AsyncMock()
    # "某种新关系" 不在 _PREDICATE_MAP → None
    bad_json = ('{"entities":[],"relations":[{'
                '"subject_name":"甲公司","subject_type":"org",'
                '"object_name":"某事件","object_type":"event",'
                '"predicate":"某种新关系","evidence":"...","confidence":0.5}]}')
    llm.complete = AsyncMock(return_value=_Resp(bad_json))
    cm = ContentMiner(llm=llm)
    entities, relations, unmapped = await cm.mine(
        [{"original_id": 1, "clean_content": "正文"}]
    )
    assert relations == []
    assert len(unmapped) == 1
    u = unmapped[0]
    assert u["relation"] == "某种新关系"
    assert u["subject_name"] == "甲公司" and u["subject_type"] == "org"
    assert u["object_name"] == "某事件" and u["object_type"] == "event"
    assert u["evidence"] == "..." and u["confidence"] == 0.5
    assert u["source_doc_id"] == "1"
