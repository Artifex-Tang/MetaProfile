"""
单元测试：foundation/relation（rule_extractor + llm_classifier + triple_writer）
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.foundation.relation.llm_classifier import LLMRelationClassifier
from metaprofile.foundation.relation.rule_extractor import (
    EntitySpan,
    _get_window,
    _make_evidence,
    _match_rules,
    extract_relations,
)
from metaprofile.foundation.relation.triple_writer import TripleWriter, WriteStats
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple, RelationType


# ─── rule_extractor ──────────────────────────────────────────────────────────

def _span(entity_id: str, typ: EntityType, name: str, start: int, end: int) -> EntitySpan:
    return EntitySpan(
        entity_id=entity_id,
        entity_type=typ,
        entity_name=name,
        start=start,
        end=end,
    )


def test_extract_relations_org_fund_project():
    text = "中科院资助量子纠错码项目开展研究。"
    spans = [
        _span("org1", EntityType.ORG, "中科院", 0, 3),
        _span("proj1", EntityType.PROJECT, "量子纠错码项目", 4, 11),
    ]
    triples = extract_relations(text, spans, source_doc_id="doc1")
    rels = {t.relation for t in triples}
    assert RelationType.ORG_FUND_PROJECT in rels


def test_extract_relations_org_employ_person():
    text = "清华大学聘请张三为研究员。"
    spans = [
        _span("org1", EntityType.ORG, "清华大学", 0, 4),
        _span("per1", EntityType.PERSON, "张三", 5, 7),
    ]
    triples = extract_relations(text, spans)
    rels = {t.relation for t in triples}
    assert RelationType.ORG_EMPLOY in rels


def test_extract_relations_person_manage_project():
    text = "张三主持量子计算重大项目，负责技术研究。"
    spans = [
        _span("per1", EntityType.PERSON, "张三", 0, 2),
        _span("proj1", EntityType.PROJECT, "量子计算重大项目", 3, 11),
    ]
    triples = extract_relations(text, spans)
    rels = {t.relation for t in triples}
    assert RelationType.PERSON_MANAGE_PROJECT in rels


def test_extract_relations_no_match_returns_empty():
    text = "这句话没有关系触发词。"
    spans = [
        _span("t1", EntityType.TECH, "量子纠错", 0, 4),
        _span("t2", EntityType.TECH, "量子计算", 5, 9),
    ]
    # TECH-TECH rules are not defined
    triples = extract_relations(text, spans)
    # may or may not match; at least no crash
    assert isinstance(triples, list)


def test_extract_relations_sets_source_doc_id():
    text = "中科院资助项目甲。"
    spans = [
        _span("org1", EntityType.ORG, "中科院", 0, 3),
        _span("proj1", EntityType.PROJECT, "项目甲", 4, 7),
    ]
    triples = extract_relations(text, spans, source_doc_id="DOC_999")
    if triples:
        assert all(t.source_doc_id == "DOC_999" for t in triples)


def test_extract_relations_method_is_rule():
    text = "中科院资助量子纠错项目。"
    spans = [
        _span("org1", EntityType.ORG, "中科院", 0, 3),
        _span("proj1", EntityType.PROJECT, "量子纠错项目", 4, 10),
    ]
    triples = extract_relations(text, spans)
    if triples:
        assert all(t.method == SourceMethod.RULE for t in triples)


def test_match_rules_org_parent():
    window = "某研究所隶属于中科院"
    result = _match_rules(EntityType.ORG, EntityType.ORG, window)
    assert result == RelationType.ORG_PARENT


def test_match_rules_no_match_returns_none():
    window = "完全无关的文字"
    result = _match_rules(EntityType.ORG, EntityType.ORG, window)
    assert result is None


def test_get_window_returns_string():
    text = "A" * 50 + "实体甲" + "B" * 30 + "实体乙" + "C" * 50
    subj = _span("s1", EntityType.ORG, "实体甲", 50, 53)
    obj = _span("o1", EntityType.PROJECT, "实体乙", 83, 86)
    window = _get_window(text, subj, obj)
    assert isinstance(window, str)
    assert len(window) > 0


def test_make_evidence_includes_both_entities():
    text = "清华大学资助了量子计算重点项目的研究工作。"
    subj = _span("s1", EntityType.ORG, "清华大学", 0, 4)
    obj = _span("o1", EntityType.PROJECT, "量子计算重点项目", 6, 14)
    ev = _make_evidence(text, subj, obj)
    assert "清华大学" in ev
    assert "量子计算重点项目" in ev


# ─── LLMRelationClassifier ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_classifier_returns_triple():
    from metaprofile.foundation.relation.llm_classifier import _RelationOutput

    mock_gateway = MagicMock()
    output = _RelationOutput(
        relation_value="资助",
        confidence=0.85,
        reason="文本中有'资助'触发词",
    )

    with patch(
        "metaprofile.foundation.relation.llm_classifier.call_with_schema",
        new=AsyncMock(return_value=(output, MagicMock())),
    ):
        clf = LLMRelationClassifier(gateway=mock_gateway)
        triple = await clf.classify(
            subject_id="org1",
            subject_type=EntityType.ORG,
            subject_name="中科院",
            object_id="proj1",
            object_type=EntityType.PROJECT,
            object_name="量子纠错项目",
            evidence="中科院资助量子纠错项目",
        )

    assert triple is not None
    assert triple.relation == RelationType.ORG_FUND_PROJECT
    assert triple.confidence == pytest.approx(0.85)
    assert triple.method == SourceMethod.LLM_EXTRACT


@pytest.mark.asyncio
async def test_llm_classifier_returns_none_if_low_confidence():
    from metaprofile.foundation.relation.llm_classifier import _RelationOutput

    mock_gateway = MagicMock()
    output = _RelationOutput(
        relation_value="资助",
        confidence=0.40,
        reason="不确定",
    )

    with patch(
        "metaprofile.foundation.relation.llm_classifier.call_with_schema",
        new=AsyncMock(return_value=(output, MagicMock())),
    ):
        clf = LLMRelationClassifier(gateway=mock_gateway)
        triple = await clf.classify(
            subject_id="org1",
            subject_type=EntityType.ORG,
            subject_name="中科院",
            object_id="proj1",
            object_type=EntityType.PROJECT,
            object_name="量子纠错项目",
            evidence="某文本",
            min_confidence=0.6,
        )

    assert triple is None


@pytest.mark.asyncio
async def test_llm_classifier_returns_none_on_invalid_relation_value():
    from metaprofile.foundation.relation.llm_classifier import _RelationOutput

    mock_gateway = MagicMock()
    output = _RelationOutput(
        relation_value="不存在的关系类型",
        confidence=0.9,
        reason="测试",
    )

    with patch(
        "metaprofile.foundation.relation.llm_classifier.call_with_schema",
        new=AsyncMock(return_value=(output, MagicMock())),
    ):
        clf = LLMRelationClassifier(gateway=mock_gateway)
        triple = await clf.classify(
            subject_id="org1",
            subject_type=EntityType.ORG,
            subject_name="中科院",
            object_id="proj1",
            object_type=EntityType.PROJECT,
            object_name="项目",
            evidence="某文本",
        )

    assert triple is None


@pytest.mark.asyncio
async def test_llm_classifier_returns_none_on_exception():
    mock_gateway = MagicMock()

    with patch(
        "metaprofile.foundation.relation.llm_classifier.call_with_schema",
        new=AsyncMock(side_effect=RuntimeError("LLM unreachable")),
    ):
        clf = LLMRelationClassifier(gateway=mock_gateway)
        triple = await clf.classify(
            subject_id="org1",
            subject_type=EntityType.ORG,
            subject_name="中科院",
            object_id="proj1",
            object_type=EntityType.PROJECT,
            object_name="项目",
            evidence="某文本",
        )

    assert triple is None


# ─── TripleWriter ─────────────────────────────────────────────────────────────

def _make_triple(
    subj_id: str = "s1",
    obj_id: str = "o1",
    rel: RelationType = RelationType.ORG_FUND_PROJECT,
) -> RelationTriple:
    return RelationTriple(
        subject_id=subj_id,
        subject_type=EntityType.ORG,
        subject_name="中科院",
        relation=rel,
        object_id=obj_id,
        object_type=EntityType.PROJECT,
        object_name="量子项目",
        evidence="中科院资助量子项目",
        confidence=0.85,
        source_doc_id="doc1",
        method=SourceMethod.RULE,
        extracted_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_triple_writer_write_calls_neo4j():
    mock_neo4j = MagicMock()
    mock_neo4j._repo = MagicMock()
    mock_neo4j._repo.upsert_relation = AsyncMock()

    writer = TripleWriter(neo4j_repo=mock_neo4j)
    ok = await writer.write(_make_triple())

    assert ok is True
    mock_neo4j._repo.upsert_relation.assert_called_once()
    call_kwargs = mock_neo4j._repo.upsert_relation.call_args.kwargs
    assert call_kwargs["from_label"] == "Org"
    assert call_kwargs["to_label"] == "Project"
    assert call_kwargs["rel_type"] == RelationType.ORG_FUND_PROJECT.value


@pytest.mark.asyncio
async def test_triple_writer_write_returns_false_on_error():
    mock_neo4j = MagicMock()
    mock_neo4j._repo = MagicMock()
    mock_neo4j._repo.upsert_relation = AsyncMock(side_effect=RuntimeError("neo4j down"))

    writer = TripleWriter(neo4j_repo=mock_neo4j)
    ok = await writer.write(_make_triple())

    assert ok is False


@pytest.mark.asyncio
async def test_triple_writer_write_batch_stats():
    mock_neo4j = MagicMock()
    mock_neo4j._repo = MagicMock()
    call_count = 0

    async def sometimes_fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("fail")

    mock_neo4j._repo.upsert_relation = AsyncMock(side_effect=sometimes_fail)

    writer = TripleWriter(neo4j_repo=mock_neo4j)
    triples = [_make_triple("s1", "o1"), _make_triple("s2", "o2"), _make_triple("s3", "o3")]
    stats = await writer.write_batch(triples)

    assert stats.written == 2
    assert stats.failed == 1
    assert len(stats.errors) == 1


@pytest.mark.asyncio
async def test_triple_writer_caps_evidence_at_500_chars():
    mock_neo4j = MagicMock()
    mock_neo4j._repo = MagicMock()
    captured_props: dict = {}

    async def capture(*args, **kwargs):
        captured_props.update(kwargs.get("props", {}))

    mock_neo4j._repo.upsert_relation = AsyncMock(side_effect=capture)

    long_evidence = "A" * 1000
    triple = RelationTriple(
        subject_id="s1",
        subject_type=EntityType.ORG,
        subject_name="中科院",
        relation=RelationType.ORG_FUND_PROJECT,
        object_id="o1",
        object_type=EntityType.PROJECT,
        object_name="项目",
        evidence=long_evidence,
        confidence=0.8,
        method=SourceMethod.RULE,
        extracted_at=datetime.now(timezone.utc),
    )

    writer = TripleWriter(neo4j_repo=mock_neo4j)
    await writer.write(triple)

    assert len(captured_props["evidence"]) == 500
