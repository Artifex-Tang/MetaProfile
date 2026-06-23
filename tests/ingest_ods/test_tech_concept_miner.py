"""Task 3: L2 tech-term miner (含 name_cn 英文归一)。"""
import json
from unittest.mock import AsyncMock, MagicMock

from metaprofile.ingest_ods.services.tech_concept_miner import TechConceptMiner


def _llm(resp_json: str):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=MagicMock(content=resp_json))
    return llm


async def test_mine_parses_terms():
    llm = _llm(json.dumps({"terms": [
        {"term": "质谱仪", "type": "设备", "confidence": 0.95, "name_cn": "质谱仪"},
        {"term": "液相色谱", "type": "方法", "confidence": 0.8, "name_cn": "液相色谱"},
    ]}))
    miner = TechConceptMiner(llm=llm)
    out = await miner.mine(title="质谱仪采购", abstract="采用液相色谱-质谱联用...")
    assert len(out) == 2
    assert out[0].term == "质谱仪"
    assert out[0].confidence == 0.95
    assert out[0].name_cn == "质谱仪"


async def test_mine_translates_english_term():
    # 英文源术语 → name_cn 给中文规范名(归一)
    llm = _llm(json.dumps({"terms": [
        {"term": "mass spectrometry", "type": "方法", "confidence": 0.9, "name_cn": "质谱法"},
    ]}))
    miner = TechConceptMiner(llm=llm)
    out = await miner.mine(title="mass spectrometry", abstract="...")
    assert out[0].term == "mass spectrometry"
    assert out[0].name_cn == "质谱法"


async def test_mine_bad_json_returns_empty():
    llm = _llm("not json")
    miner = TechConceptMiner(llm=llm)
    assert await miner.mine(title="x", abstract="y") == []


async def test_mine_empty_title_returns_empty_without_call():
    llm = _llm(json.dumps({"terms": [{"term": "x", "type": "", "confidence": 0.1, "name_cn": ""}]}))
    miner = TechConceptMiner(llm=llm)
    out = await miner.mine(title="   ", abstract="y")
    assert out == []
    llm.complete.assert_not_awaited()
