"""
单元测试：foundation/disambiguation（candidate_recall + llm_judge + merger）
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.foundation.disambiguation.candidate_recall import (
    CandidatePair,
    CandidateRecaller,
)
from metaprofile.foundation.disambiguation.llm_judge import (
    DisambiguationVerdict,
    LLMDisambiguator,
)
from metaprofile.foundation.disambiguation.merger import (
    EntityMerger,
    MergeResult,
    _is_empty,
    _merge_attributes,
)
from metaprofile.shared.schemas.base import EntityType


# ─── CandidateRecaller ────────────────────────────────────────────────────────

def _make_hit(entity_id: str, name_cn: str, score: float) -> dict:
    return {"entity_id": entity_id, "tech_name_cn": name_cn, "_score": score}


@pytest.mark.asyncio
async def test_recall_splits_into_three_buckets():
    emb = AsyncMock()
    emb.embed_one = AsyncMock(return_value=[0.1] * 128)

    es = AsyncMock()
    es.knn_search = AsyncMock(
        return_value=[
            _make_hit("e1", "量子纠错A", 0.97),   # auto_merge
            _make_hit("e2", "量子纠错B", 0.82),   # need_judge
            _make_hit("e3", "量子纠错C", 0.55),   # discard
        ]
    )

    recaller = CandidateRecaller(embedding_client=emb, es_repo=es)
    auto, judge, discard = await recaller.recall(
        entity_type=EntityType.TECH, query_text="量子纠错"
    )

    assert len(auto) == 1 and auto[0].candidate_id == "e1"
    assert len(judge) == 1 and judge[0].candidate_id == "e2"
    assert len(discard) == 1 and discard[0].candidate_id == "e3"


@pytest.mark.asyncio
async def test_recall_candidate_name_uses_entity_type_field():
    emb = AsyncMock()
    emb.embed_one = AsyncMock(return_value=[0.0] * 128)

    es = AsyncMock()
    # ORG → name field is org_name_cn
    es.knn_search = AsyncMock(
        return_value=[{"entity_id": "o1", "org_name_cn": "中科院", "_score": 0.96}]
    )

    recaller = CandidateRecaller(embedding_client=emb, es_repo=es)
    auto, _, _ = await recaller.recall(
        entity_type=EntityType.ORG, query_text="中国科学院"
    )
    assert auto[0].candidate_name == "中科院"


@pytest.mark.asyncio
async def test_recall_raw_data_excludes_underscore_fields():
    emb = AsyncMock()
    emb.embed_one = AsyncMock(return_value=[0.0] * 128)

    es = AsyncMock()
    es.knn_search = AsyncMock(
        return_value=[{"entity_id": "t1", "tech_name_cn": "AI", "_score": 0.96, "_id": "t1"}]
    )

    recaller = CandidateRecaller(embedding_client=emb, es_repo=es)
    auto, _, _ = await recaller.recall(
        entity_type=EntityType.TECH, query_text="AI"
    )
    assert "_score" not in auto[0].raw_data
    assert "_id" not in auto[0].raw_data
    assert "entity_id" in auto[0].raw_data


@pytest.mark.asyncio
async def test_recall_empty_hits():
    emb = AsyncMock()
    emb.embed_one = AsyncMock(return_value=[0.0] * 128)

    es = AsyncMock()
    es.knn_search = AsyncMock(return_value=[])

    recaller = CandidateRecaller(embedding_client=emb, es_repo=es)
    auto, judge, discard = await recaller.recall(
        entity_type=EntityType.TECH, query_text="无匹配实体"
    )
    assert auto == [] and judge == [] and discard == []


# ─── LLMDisambiguator ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_disambiguator_returns_verdict():
    mock_gateway = MagicMock()
    verdict = DisambiguationVerdict(
        is_same=True,
        reason="名称高度相似，地址一致",
        merge_to="entity_a",
        confidence=0.92,
    )

    with patch(
        "metaprofile.foundation.disambiguation.llm_judge.call_with_schema",
        new=AsyncMock(return_value=(verdict, MagicMock())),
    ):
        disamb = LLMDisambiguator(gateway=mock_gateway)
        result = await disamb.judge(
            entity_type=EntityType.ORG,
            entity_a={"entity_id": "entity_a", "org_name_cn": "中科院计算所"},
            entity_b={"entity_id": "entity_b", "org_name_cn": "计算技术研究所"},
        )

    assert result.is_same is True
    assert result.merge_to == "entity_a"
    assert result.confidence == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_llm_disambiguator_not_same():
    mock_gateway = MagicMock()
    verdict = DisambiguationVerdict(
        is_same=False,
        reason="不同机构，领域不同",
        merge_to="entity_a",
        confidence=0.88,
    )

    with patch(
        "metaprofile.foundation.disambiguation.llm_judge.call_with_schema",
        new=AsyncMock(return_value=(verdict, MagicMock())),
    ):
        disamb = LLMDisambiguator(gateway=mock_gateway)
        result = await disamb.judge(
            entity_type=EntityType.ORG,
            entity_a={"entity_id": "entity_a", "org_name_cn": "清华大学"},
            entity_b={"entity_id": "entity_b", "org_name_cn": "北京大学"},
        )

    assert result.is_same is False


# ─── _merge_attributes ────────────────────────────────────────────────────────

def test_merge_attributes_fills_empty_fields():
    to = {"name": "量子纠错", "domain": None, "summary": ""}
    frm = {"name": "量子纠错码", "domain": "量子计算", "summary": "一种纠错技术"}
    merged, filled = _merge_attributes(to, frm)
    assert merged["domain"] == "量子计算"
    assert merged["summary"] == "一种纠错技术"
    assert merged["name"] == "量子纠错"  # to value kept
    assert "domain" in filled
    assert "summary" in filled


def test_merge_attributes_confidence_takes_max():
    to = {"confidence": 0.7}
    frm = {"confidence": 0.9}
    merged, filled = _merge_attributes(to, frm)
    assert merged["confidence"] == pytest.approx(0.9)
    assert "confidence" in filled


def test_merge_attributes_confidence_keeps_to_if_higher():
    to = {"confidence": 0.95}
    frm = {"confidence": 0.80}
    merged, _ = _merge_attributes(to, frm)
    assert merged["confidence"] == pytest.approx(0.95)


def test_merge_attributes_skips_empty_from_values():
    to = {"name": "量子纠错"}
    frm = {"name": None, "domain": []}
    merged, filled = _merge_attributes(to, frm)
    assert merged["name"] == "量子纠错"
    assert filled == []


def test_is_empty():
    assert _is_empty(None)
    assert _is_empty("")
    assert _is_empty("   ")
    assert _is_empty([])
    assert _is_empty({})
    assert not _is_empty("hello")
    assert not _is_empty(0)
    assert not _is_empty(["a"])


# ─── EntityMerger ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_entity_merger_merges_and_deletes():
    unified_repo = MagicMock()
    unified_repo.get_entity = AsyncMock(
        side_effect=[
            {"entity_id": "to", "name": "量子纠错", "domain": None},   # merge_to
            {"entity_id": "from", "name": "量子纠错码", "domain": "量子计算"},  # merge_from
        ]
    )
    unified_repo.upsert_entity = AsyncMock()
    unified_repo.delete_entity = AsyncMock()
    unified_repo._neo4j = None  # skip neo4j redirect

    merger = EntityMerger(unified_repo=unified_repo)
    result = await merger.merge(
        entity_type=EntityType.TECH,
        merge_to_id="to",
        merge_from_id="from",
    )

    assert result.merge_to_id == "to"
    assert result.merge_from_id == "from"
    assert "domain" in result.merged_fields

    unified_repo.upsert_entity.assert_called_once()
    unified_repo.delete_entity.assert_called_once_with(EntityType.TECH, "from")


@pytest.mark.asyncio
async def test_entity_merger_raises_if_entity_not_found():
    unified_repo = MagicMock()
    unified_repo.get_entity = AsyncMock(return_value=None)

    merger = EntityMerger(unified_repo=unified_repo)
    with pytest.raises(ValueError, match="merge_to entity not found"):
        await merger.merge(
            entity_type=EntityType.TECH,
            merge_to_id="missing",
            merge_from_id="from",
        )
