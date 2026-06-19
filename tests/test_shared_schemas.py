"""单元测试：shared/schemas 校验规则（无外部依赖）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from metaprofile.shared.schemas.base import EntityType, ReviewType, SourceMethod
from metaprofile.shared.schemas.entity_tech import TechExtractionResult, TechProfile
from metaprofile.shared.schemas.entity_org import OrgProfile
from metaprofile.shared.schemas.entity_person import PersonProfile
from metaprofile.shared.schemas.entity_project import ProjectProfile
from metaprofile.shared.schemas.relations import RelationTriple, RelationType


# ─── TechProfile ────────────────────────────────────────────────────────────

TECH_REQUIRED = {
    "tech_name_cn": "量子纠错码",
    "tech_name_en": "Quantum Error Correction",
    "tech_domain": ["量子计算"],
    "tech_summary": "利用多个物理量子比特编码一个逻辑量子比特，以抵抗噪声。",
    "current_status": "观点1：仍处于研究阶段；观点2：已有部分实验验证。",
    "trend": "观点1：将向容错量子计算演进。",
}


def test_tech_profile_valid():
    p = TechProfile(**TECH_REQUIRED)
    assert p.tech_name_cn == "量子纠错码"
    assert p.confidence == 0.0


def test_tech_profile_missing_required():
    # name/domain 字段已放宽为可选(容 ingest 稀疏真数据)，
    # 仍必填的是 tech_summary/current_status/trend
    with pytest.raises(ValidationError) as exc_info:
        TechProfile(tech_name_cn="X")
    errors = exc_info.value.errors()
    missing = {e["loc"][0] for e in errors}
    assert "tech_summary" in missing
    assert "current_status" in missing
    assert "trend" in missing


def test_tech_profile_extra_field_forbidden():
    with pytest.raises(ValidationError):
        TechProfile(**TECH_REQUIRED, unknown_field="x")


def test_tech_profile_sparse_allowed():
    # 稀疏真数据：空 name / 空 domain 必须通过校验
    p = TechProfile(**{**TECH_REQUIRED, "tech_domain": []})
    assert p.tech_domain == []
    p2 = TechProfile(
        tech_summary="s",
        current_status="c",
        trend="t",
        tech_name_cn="",
        tech_name_en="",
        tech_domain=[],
    )
    assert p2.tech_name_cn == ""


def test_tech_extraction_result():
    r = TechExtractionResult(
        tech_name_cn="量子纠错",
        tech_domain=["量子计算"],
        tech_summary="摘要",
        current_status="现状",
        trend="趋势",
        confidence=0.85,
    )
    assert r.confidence == 0.85
    assert r.tech_name_en is None


# ─── RelationTriple ──────────────────────────────────────────────────────────

from datetime import datetime


def test_relation_triple_valid():
    rt = RelationTriple(
        subject_id="TECH_001",
        subject_type=EntityType.TECH,
        relation=RelationType.TECH_CONTRIBUTOR,
        object_id="ORG_001",
        object_type=EntityType.ORG,
        confidence=0.9,
        method=SourceMethod.RULE,
        extracted_at=datetime.utcnow(),
    )
    assert rt.relation == RelationType.TECH_CONTRIBUTOR


def test_relation_triple_confidence_out_of_range():
    with pytest.raises(ValidationError):
        RelationTriple(
            subject_id="T1",
            subject_type=EntityType.TECH,
            relation=RelationType.TECH_CONTRIBUTOR,
            object_id="O1",
            object_type=EntityType.ORG,
            confidence=1.5,  # > 1.0
            method=SourceMethod.RULE,
            extracted_at=datetime.utcnow(),
        )
