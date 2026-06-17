"""结构化关系物化规则测试（GAP 1）。"""
from __future__ import annotations

from metaprofile.ingest_ods.domain.relation_rules import (
    extract_structured_relations,
)
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationType


def test_company_legal_person_becomes_org_employ_edge() -> None:
    """company.legal_person_name → ORG_EMPLOY 边(主体=PK org, 客体=name:person)。"""
    row = {"company_id": 1, "legal_person_name": "张三"}
    triples = extract_structured_relations(
        "ods_company_basic_info", row, "1", EntityType.ORG,
    )
    assert len(triples) == 1
    tri = triples[0]
    assert tri.subject_id == "1"
    assert tri.subject_type == EntityType.ORG
    assert tri.relation == RelationType.ORG_EMPLOY
    assert tri.object_id == "name:张三"
    assert tri.object_type == EntityType.PERSON
    assert tri.object_name == "张三"
    assert tri.method == SourceMethod.RULE
    assert tri.confidence == 1.0


def test_patent_inventor_list_becomes_tech_contributor_edges() -> None:
    """patent features.Inventor=["A","B"] → 2 条 TECH_CONTRIBUTOR(主体=person, 客体=PK tech)。"""
    row = {
        "title": "一种装置",
        "applicant": "甲公司",
        "features": '{"Inventor": ["A", "B"]}',
    }
    triples = extract_structured_relations(
        "ods_invention_patent_cn", row, "PAT1", EntityType.TECH,
    )
    # applicant → 1 ORG_INVOLVE_TECH(org 主体, tech 客体)；Inventor → 2 TECH_CONTRIBUTOR
    involve = [t for t in triples if t.relation == RelationType.ORG_INVOLVE_TECH]
    contrib = [t for t in triples if t.relation == RelationType.TECH_CONTRIBUTOR]
    assert len(involve) == 1
    assert len(contrib) == 2

    # applicant: org 主体 → tech 客体(current)
    assert involve[0].subject_id == "name:甲公司"
    assert involve[0].subject_type == EntityType.ORG
    assert involve[0].object_id == "PAT1"
    assert involve[0].object_type == EntityType.TECH

    # 每个 Inventor → 一条 person→tech
    contrib_names = sorted(t.subject_name for t in contrib)
    assert contrib_names == ["A", "B"]
    for t in contrib:
        assert t.subject_type == EntityType.PERSON
        assert t.subject_id.startswith("name:")
        assert t.object_id == "PAT1"
        assert t.object_type == EntityType.TECH
        assert t.relation == RelationType.TECH_CONTRIBUTOR


def test_talent_employer_becomes_affiliated_edge() -> None:
    """talent.employer → PERSON_AFFILIATED_ORG(person 主体, org 客体)。"""
    row = {"full_name": "李四", "employer": "乙所"}
    triples = extract_structured_relations(
        "ods_talent_info_cn", row, "P1", EntityType.PERSON,
    )
    assert len(triples) == 1
    tri = triples[0]
    assert tri.subject_id == "P1"
    assert tri.subject_type == EntityType.PERSON
    assert tri.relation == RelationType.PERSON_AFFILIATED_ORG
    assert tri.object_id == "name:乙所"
    assert tri.object_type == EntityType.ORG


def test_science_authors_comma_string_splits() -> None:
    """science authors 既支持 list 也支持逗号/分号串 → 每作者一条 TECH_CONTRIBUTOR。"""
    row = {"title": "论文X", "authors": "张三, 李四; 王五"}
    triples = extract_structured_relations(
        "ods_science_literature", row, "TECH1", EntityType.TECH,
    )
    assert len(triples) == 3
    names = sorted(t.subject_name for t in triples)
    assert names == ["张三", "李四", "王五"]


def test_unknown_table_returns_empty() -> None:
    """未注册表 → []。"""
    triples = extract_structured_relations(
        "ods_unknown_table", {"x": 1}, "X1", EntityType.ORG,
    )
    assert triples == []


def test_missing_field_no_edge() -> None:
    """字段缺失/空 → 不产生边。"""
    row = {"company_id": 1, "legal_person_name": None}
    triples = extract_structured_relations(
        "ods_company_basic_info", row, "1", EntityType.ORG,
    )
    assert triples == []
