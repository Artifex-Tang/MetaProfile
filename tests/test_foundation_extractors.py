"""
单元测试：foundation/extractors（rules 纯逻辑 + LLMFunctionExtractor mock）
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.foundation.extractors.llm_function import (
    LLMFunctionExtractor,
    _build_context,
)
from metaprofile.foundation.extractors.rules import extract_rules
from metaprofile.foundation.ner.bert_crf import NERSpan
from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.schemas.entity_tech import TechExtractionResult


# ─── rules.py ───────────────────────────────────────────────────────────────

class TestRulesPatent:
    def test_extracts_application_number(self):
        fields = {"application_number": "CN202310001234.1", "title": "量子纠错"}
        result = extract_rules("patent", fields)
        assert result["application_number"] == "CN202310001234.1"

    def test_extracts_cn_patent_from_raw_field(self):
        fields = {"raw_AN": "申请号 CN202310001234A", "title": "专利"}
        result = extract_rules("patent", fields)
        assert "cn_patent_number" in result

    def test_parses_ipc_list(self):
        fields = {"ipc_codes": ["G06N 10/70", "H01L 39/00"]}
        result = extract_rules("patent", fields)
        assert result["ipc_codes"] == ["G06N 10/70", "H01L 39/00"]

    def test_parses_ipc_string(self):
        fields = {"raw_IPC": "G06N 10/70; H01L 39/00"}
        result = extract_rules("patent", fields)
        assert len(result.get("ipc_codes", [])) >= 1

    def test_parses_application_date(self):
        fields = {"application_date": "2023-01-15"}
        result = extract_rules("patent", fields)
        assert result["application_date"] == date(2023, 1, 15)

    def test_unknown_doc_type_returns_empty(self):
        assert extract_rules("unknown_type", {"x": 1}) == {}


class TestRulesPaper:
    def test_extracts_doi(self):
        fields = {"doi": "10.1038/s41586-023-00001-1"}
        result = extract_rules("paper", fields)
        assert result["doi"] == "10.1038/s41586-023-00001-1"

    def test_splits_authors_semicolon(self):
        fields = {"authors": "张三;李四;王五"}
        result = extract_rules("paper", fields)
        assert result["authors"] == ["张三", "李四", "王五"]

    def test_splits_authors_comma(self):
        fields = {"authors": "Zhang San, Li Si"}
        result = extract_rules("paper", fields)
        assert len(result["authors"]) == 2

    def test_authors_list_passthrough(self):
        fields = {"authors": ["张三", "李四"]}
        result = extract_rules("paper", fields)
        assert result["authors"] == ["张三", "李四"]

    def test_splits_keywords(self):
        fields = {"keywords": "量子计算;量子纠错;量子比特"}
        result = extract_rules("paper", fields)
        assert "量子计算" in result["keywords"]

    def test_parses_publish_date(self):
        fields = {"publish_date": "2023-06"}
        result = extract_rules("paper", fields)
        assert result["publish_date"] == date(2023, 6, 1)


class TestRulesProject:
    def test_extracts_project_number(self):
        fields = {"project_number": "62271234"}
        result = extract_rules("project", fields)
        assert result["project_number"] == "62271234"

    def test_finds_8_digit_number_in_title(self):
        fields = {"title": "基金项目编号62271234研究量子计算"}
        result = extract_rules("project", fields)
        assert result.get("project_number") == "62271234"

    def test_start_year_to_date(self):
        fields = {"start_year": "2022"}
        result = extract_rules("project", fields)
        assert result["start_date"] == date(2022, 1, 1)


class TestRulesEnterprise:
    def test_extracts_establish_date(self):
        fields = {"establish_date": "2010-03-15"}
        result = extract_rules("enterprise", fields)
        assert result["establish_date"] == date(2010, 3, 15)

    def test_extracts_reg_capital_number(self):
        fields = {"reg_capital": "注册资本5000万人民币"}
        result = extract_rules("enterprise", fields)
        assert result.get("reg_capital_amount") == pytest.approx(5000.0)

    def test_reg_capital_with_comma(self):
        fields = {"reg_capital": "1,000,000元"}
        result = extract_rules("enterprise", fields)
        assert result.get("reg_capital_amount") == pytest.approx(1000000.0)


class TestRulesTender:
    def test_extracts_budget_amount(self):
        fields = {"budget_amount": "预算金额：200万元"}
        result = extract_rules("tender", fields)
        assert result.get("budget_amount") == pytest.approx(200.0)


# ─── LLMFunctionExtractor ────────────────────────────────────────────────────

def make_span(text: str, label: EntityType, conf: float = 0.9) -> NERSpan:
    return NERSpan(text=text, label=label, start=0, end=len(text), confidence=conf)


@pytest.mark.asyncio
async def test_llm_function_extractor_calls_correct_extractor():
    mock_gateway = MagicMock()

    tech_result = TechExtractionResult(
        tech_name_cn="量子纠错",
        tech_domain=["量子计算"],
        tech_summary="量子纠错是...",
        current_status="仍处于研究阶段",
        trend="趋势向好",
        confidence=0.88,
    )

    extractor = LLMFunctionExtractor(gateway=mock_gateway)
    # mock 内部的 TechExtractor.extract
    extractor._extractors[EntityType.TECH].extract = AsyncMock(return_value=tech_result)

    spans = [make_span("量子纠错", EntityType.TECH)]
    outputs = await extractor.extract_from_spans(
        text="量子纠错是利用多个物理量子比特编码一个逻辑量子比特的技术。",
        spans=spans,
        source_doc_id="DOC_001",
    )

    assert len(outputs) == 1
    assert outputs[0].entity_type == EntityType.TECH
    assert outputs[0].result.tech_name_cn == "量子纠错"
    assert outputs[0].source_doc_id == "DOC_001"


@pytest.mark.asyncio
async def test_llm_function_extractor_filters_low_confidence():
    mock_gateway = MagicMock()
    extractor = LLMFunctionExtractor(gateway=mock_gateway)

    spans = [make_span("低置信度实体", EntityType.TECH, conf=0.3)]
    outputs = await extractor.extract_from_spans(
        text="低置信度实体是...",
        spans=spans,
        min_confidence=0.7,  # 0.3 < 0.7 → 过滤
    )
    assert outputs == []


@pytest.mark.asyncio
async def test_llm_function_extractor_handles_extraction_error():
    mock_gateway = MagicMock()
    extractor = LLMFunctionExtractor(gateway=mock_gateway)
    extractor._extractors[EntityType.ORG].extract = AsyncMock(
        side_effect=RuntimeError("LLM unreachable")
    )

    spans = [make_span("某机构", EntityType.ORG)]
    outputs = await extractor.extract_from_spans(text="某机构成立于2000年", spans=spans)
    # 错误被捕获，不抛出，返回空列表
    assert outputs == []


def test_build_context_center_span():
    text = "A" * 1000 + "目标实体" + "B" * 1000
    span = NERSpan(text="目标实体", label=EntityType.TECH, start=1000, end=1004, confidence=0.9)
    ctx = _build_context(text, span)
    assert "目标实体" in ctx
    assert len(ctx) <= 2001  # MAX_TEXT_CHARS + 1（省略号）


def test_build_context_start_of_text():
    text = "目标实体" + "X" * 2000
    span = NERSpan(text="目标实体", label=EntityType.TECH, start=0, end=4, confidence=0.9)
    ctx = _build_context(text, span)
    assert ctx.startswith("目标实体")


def test_build_context_end_of_text():
    text = "X" * 2000 + "目标实体"
    span = NERSpan(text="目标实体", label=EntityType.TECH, start=2000, end=2004, confidence=0.9)
    ctx = _build_context(text, span)
    assert "目标实体" in ctx
