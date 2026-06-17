"""name→PK 索引测试（GAP 2）。"""
from __future__ import annotations

from metaprofile.ingest_ods.services.name_index import NameIndex, _norm_name
from metaprofile.shared.schemas.base import EntityType


def test_resolve_hit_returns_pk() -> None:
    idx = NameIndex()
    idx.add(EntityType.ORG, "1", {"name_cn": "甲公司"})
    assert idx.resolve(EntityType.ORG, "甲公司") == "1"


def test_resolve_miss_returns_name_satellite() -> None:
    idx = NameIndex()
    idx.add(EntityType.ORG, "1", {"name_cn": "甲公司"})
    assert idx.resolve(EntityType.ORG, "乙") == "name:乙"


def test_resolve_type_scoped() -> None:
    """同 name 不同 type 不混淆。"""
    idx = NameIndex()
    idx.add(EntityType.ORG, "O1", {"name_cn": "甲"})
    idx.add(EntityType.PERSON, "P1", {"name_cn": "甲"})
    assert idx.resolve(EntityType.ORG, "甲") == "O1"
    assert idx.resolve(EntityType.PERSON, "甲") == "P1"


def test_list_name_normalized_to_first() -> None:
    """attrs.name_cn 可能是 list（project）→ 取首元素。"""
    idx = NameIndex()
    idx.add(EntityType.PROJECT, "PRJ1", {"name_cn": ["M1", "M2"]})
    assert idx.resolve(EntityType.PROJECT, "M1") == "PRJ1"


def test_tech_name_cn_fallback() -> None:
    """无 name_cn 时 fallback 到 tech_name_cn。"""
    idx = NameIndex()
    idx.add(EntityType.TECH, "T1", {"tech_name_cn": "装置X"})
    assert idx.resolve(EntityType.TECH, "装置X") == "T1"


def test_norm_name_picks_first_available() -> None:
    assert _norm_name({"name_cn": "甲"}) == "甲"
    assert _norm_name({"tech_name_cn": "T"}) == "T"
    assert _norm_name({"name_cn": ["L1"]}) == "L1"
    assert _norm_name({"name_cn": None, "tech_name_cn": "T"}) == "T"
    assert _norm_name({}) is None
    assert _norm_name({"name_cn": ""}) is None


def test_add_skips_when_no_name() -> None:
    """无 name 字段 → 不入索引,resolve 必然 miss。"""
    idx = NameIndex()
    idx.add(EntityType.ORG, "1", {"summary": "no name"})
    assert idx.resolve(EntityType.ORG, "no name") == "name:no name"
