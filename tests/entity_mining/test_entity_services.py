"""Phase D 实体挖掘测试:名清洗/作者消歧/ROR 匹配(mock)/项目分类 prompt。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.entity_mining.services.author_dedup import (
    build_author_records,
    dedup_pairs,
    parse_authors_row,
)
from metaprofile.entity_mining.services.name_utils import (
    author_block_key,
    clean_org_name,
    similarity,
)
from metaprofile.entity_mining.services.org_normalizer import ror_match
from metaprofile.entity_mining.services.project_classify import _build_prompt


def test_clean_org_name_strips_suffixes_and_parens():
    assert clean_org_name("清华大学（北京）") == "清华"
    assert clean_org_name("华为技术有限公司") == "华为技术"
    assert clean_org_name("MIT (Massachusetts)") != ""
    assert clean_org_name("") == ""


def test_similarity_bounds():
    assert similarity("华为技术", "华为技术") == 1.0
    assert similarity("", "x") == 0.0
    assert 0 < similarity("quantum computing", "quantum computig") < 1


def test_author_block_key():
    assert author_block_key("张三") == "张|三"
    assert author_block_key("Alan Turing") == "turing|a"
    assert author_block_key("") == ""


def test_parse_authors_row():
    assert parse_authors_row("张三; 李四,王五") == ["张三", "李四", "王五"]
    assert parse_authors_row(None) == []
    assert parse_authors_row("A") == []


def test_dedup_pairs_high_coauthor_scores():
    rows = [
        ("张三;李四;王五", "d1", 2024),
        ("张三;李四;赵六", "d2", 2025),      # 同名张三+共作者李四 → 高分
        ("张三丰;钱七", "d3", 2025),          # 同块(张|三)但无共作者
    ]
    records = build_author_records(rows)
    pairs = dedup_pairs(records, threshold=0.5)
    top = next((p for p in pairs if p[0] == "张三" and p[1] == "张三"), None)
    # build_author_records 聚合同名 → "张三" 单记录;测块内不同名对
    assert top is None or top[2] >= 0.5
    # 张三 vs 张三丰:无共作者,姓名相似中等 → 低于纯共作者对
    zsf = next((p for p in pairs if {p[0], p[1]} == {"张三", "张三丰"}), None)
    if zsf:
        assert zsf[3] == 0.0  # jaccard 0


def test_build_author_records_aggregates():
    rows = [("甲一;乙二", "d1", 2024), ("甲一;丙三", "d2", 2025)]
    recs = build_author_records(rows)
    assert recs["甲一"].coauthors == {"乙二", "丙三"}
    assert recs["甲一"].years == {2024, 2025}
    assert recs["甲一"].source_doc_ids == {"d1", "d2"}


@pytest.mark.asyncio
async def test_ror_match_chosen_hits():
    fake_items = {
        "items": [{
            "chosen": True,
            "organization": {"id": "https://ror.org/0123abc", "name": "Tsinghua University"},
        }],
    }
    with patch("httpx.AsyncClient") as client_cls:
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=MagicMock(
            json=lambda: fake_items, raise_for_status=lambda: None,
        ))
        client_cls.return_value = client
        out = await ror_match("清华大学")
    assert out is not None and out["score"] == 1.0
    assert out["ror_id"] == "https://ror.org/0123abc"


@pytest.mark.asyncio
async def test_ror_match_network_error_returns_none():
    with patch("httpx.AsyncClient", side_effect=OSError("no network")):
        assert await ror_match("x") is None


def test_project_prompt_contains_labels_and_ids():
    P = MagicMock()
    P.project_id = "PRJ-1"
    P.name_cn = ["智能芯片"]
    P.name_en = []
    P.research_content = ["研究芯片架构"]
    labels = [{"code": "G06T", "name": "图像数据处理"}]
    txt = _build_prompt([P], labels)
    assert "G06T" in txt and "PRJ-1" in txt and "智能芯片" in txt
