import pytest

from metaprofile.ingest_ods.llm.prompts import (
    DisambigResult, MinedEntity, MinedRelation, ScoreOutput, map_predicate,
)
from metaprofile.shared.schemas.relations import RelationType


def test_map_predicate_known() -> None:
    assert map_predicate("隶属", "person", "org") == RelationType.PERSON_AFFILIATED_ORG
    assert map_predicate("研发", "org", "tech") == RelationType.ORG_INVOLVE_TECH
    assert map_predicate("中标", "org", "project") == RelationType.ORG_UNDERTAKE_PROJECT


def test_map_predicate_unknown_returns_none() -> None:
    assert map_predicate("某种不存在的关系", "person", "org") is None


def test_mined_entity_parses() -> None:
    e = MinedEntity(type="org", name="甲公司", attrs={"summary": "x"},
                    veracity_hint=0.8, as_of="2026-01-01")
    assert e.type == "org"


def test_score_output_bounds() -> None:
    s = ScoreOutput(veracity=0.9, timeliness=0.5)
    assert 0.0 <= s.veracity <= 1.0


def test_disambig_result() -> None:
    d = DisambigResult(same=False, reason="不同机构")
    assert d.same is False
