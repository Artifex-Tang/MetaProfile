"""单元测试：shared/utils 模块（无外部依赖）。"""
from __future__ import annotations

from datetime import date

import pytest

from metaprofile.shared.utils.date_normalizer import normalize_date, to_iso_date
from metaprofile.shared.utils.id_generator import new_entity_id, stable_id_from_attrs
from metaprofile.shared.utils.text_normalizer import (
    clean_text,
    normalize_org_name,
    normalize_person_name,
    strip_org_suffix,
    truncate_text,
)
from metaprofile.shared.schemas.base import EntityType


# ─── date_normalizer ────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("2023-06-15", date(2023, 6, 15)),
    ("2023/06/15", date(2023, 6, 15)),
    ("2023年6月15日", date(2023, 6, 15)),
    ("2023.06.15", date(2023, 6, 15)),
    ("20230615", date(2023, 6, 15)),
    ("2023-06", date(2023, 6, 1)),
    ("2023年6月", date(2023, 6, 1)),
    ("2023", date(2023, 1, 1)),
    (None, None),
    ("", None),
    ("无效日期", None),
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


def test_to_iso_date():
    assert to_iso_date(date(2023, 6, 15)) == "2023-06-15"
    assert to_iso_date(None) is None


# ─── id_generator ───────────────────────────────────────────────────────────

def test_new_entity_id_format():
    eid = new_entity_id(EntityType.TECH)
    parts = eid.split("_")
    assert parts[0] == "TECH"
    assert len(parts[2]) == 8


def test_new_entity_id_unique():
    ids = {new_entity_id(EntityType.ORG) for _ in range(100)}
    assert len(ids) == 100


def test_stable_id_same_attrs():
    id1 = stable_id_from_attrs(EntityType.ORG, "中国科学院", "1949-11-01")
    id2 = stable_id_from_attrs(EntityType.ORG, "中国科学院", "1949-11-01")
    assert id1 == id2


def test_stable_id_different_attrs():
    id1 = stable_id_from_attrs(EntityType.ORG, "北京大学")
    id2 = stable_id_from_attrs(EntityType.ORG, "清华大学")
    assert id1 != id2


# ─── text_normalizer ────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,expected", [
    ("中国科学院　计算技术研究所", "中国科学院计算技术研究所"),  # 全角空格
    ("Ａ公司", "A公司"),  # 全角字母
    (None, ""),
    ("", ""),
])
def test_normalize_org_name(name, expected):
    assert normalize_org_name(name) == expected


def test_strip_org_suffix():
    assert strip_org_suffix("北京航空航天大学") == "北京航空航天"
    assert strip_org_suffix("华为技术有限公司") == "华为技术"
    assert strip_org_suffix("中国科学院") == "中国科学院"  # 研究院后缀不匹配（无单独"学院"）
    assert strip_org_suffix("中国人民大学") == "中国人民"


def test_normalize_person_name():
    assert normalize_person_name("张　三") == "张三"
    assert normalize_person_name(None) == ""


def test_clean_text():
    assert clean_text("  hello\x00world  ") == "helloworld"  # 控制字符直接移除，不替换成空格
    assert clean_text("hello  world") == "hello world"  # 多空格规范化
    assert clean_text(None) == ""
    assert clean_text("") == ""


def test_truncate_text():
    assert truncate_text("abcdefg", 5) == "abcde…"
    assert truncate_text("abc", 10) == "abc"
    assert truncate_text("你好世界", 2) == "你好…"
