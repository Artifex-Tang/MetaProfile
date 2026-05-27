"""
单元测试：foundation/ner（全部 mock HTTP）
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from metaprofile.foundation.ner.bert_crf import BertCRFNER, NERSpan
from metaprofile.foundation.ner.ensemble import EnsembleNER, _merge, _remove_overlaps
from metaprofile.foundation.ner.uie import UIENER
from metaprofile.shared.schemas.base import EntityType


def make_resp(json_data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=json_data,
        request=httpx.Request("POST", "http://test"),
    )


# ─── BertCRFNER ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bert_crf_predict_parses_spans():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=make_resp({
        "entities": [
            {"text": "量子纠错", "label": "TECH", "start": 0, "end": 4, "score": 0.95},
            {"text": "中国科学院", "label": "ORG", "start": 5, "end": 10, "score": 0.88},
        ]
    }))
    ner = BertCRFNER(client=mock_client)
    spans = await ner.predict("量子纠错中国科学院研究进展")

    assert len(spans) == 2
    assert spans[0].text == "量子纠错"
    assert spans[0].label == EntityType.TECH
    assert spans[0].confidence == pytest.approx(0.95)
    assert spans[1].label == EntityType.ORG


@pytest.mark.asyncio
async def test_bert_crf_unknown_label_skipped():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=make_resp({
        "entities": [
            {"text": "X", "label": "UNKNOWN", "start": 0, "end": 1, "score": 0.9},
            {"text": "量子计算", "label": "TECH", "start": 2, "end": 6, "score": 0.8},
        ]
    }))
    ner = BertCRFNER(client=mock_client)
    spans = await ner.predict("X量子计算")
    assert len(spans) == 1
    assert spans[0].label == EntityType.TECH


@pytest.mark.asyncio
async def test_bert_crf_empty_response():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=make_resp({"entities": []}))
    ner = BertCRFNER(client=mock_client)
    spans = await ner.predict("无实体文本")
    assert spans == []


@pytest.mark.asyncio
async def test_bert_crf_bio_label_prefix():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=make_resp({
        "entities": [{"text": "张三", "label": "B-PERSON", "start": 0, "end": 2, "score": 0.9}]
    }))
    ner = BertCRFNER(client=mock_client)
    spans = await ner.predict("张三是研究员")
    assert spans[0].label == EntityType.PERSON


# ─── UIENER ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_uie_predict_parses_result():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=make_resp({
        "result": {
            "技术": [{"text": "量子计算", "start": 0, "end": 4, "probability": 0.92}],
            "机构": [{"text": "清华大学", "start": 5, "end": 9, "probability": 0.85}],
        }
    }))
    ner = UIENER(client=mock_client)
    spans = await ner.predict("量子计算清华大学")

    labels = {s.label for s in spans}
    assert EntityType.TECH in labels
    assert EntityType.ORG in labels


@pytest.mark.asyncio
async def test_uie_unknown_schema_label_skipped():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=make_resp({
        "result": {
            "未知类型": [{"text": "X", "start": 0, "end": 1, "probability": 0.9}],
            "技术": [{"text": "量子比特", "start": 2, "end": 6, "probability": 0.88}],
        }
    }))
    ner = UIENER(client=mock_client)
    spans = await ner.predict("X量子比特")
    assert len(spans) == 1
    assert spans[0].label == EntityType.TECH


# ─── EnsembleNER ─────────────────────────────────────────────────────────────

def make_span(text: str, label: EntityType, start: int, end: int, conf: float) -> NERSpan:
    return NERSpan(text=text, label=label, start=start, end=end, confidence=conf)


def test_merge_deduplicates_same_span():
    spans_a = [make_span("量子纠错", EntityType.TECH, 0, 4, 0.80)]
    spans_b = [make_span("量子纠错", EntityType.TECH, 0, 4, 0.95)]
    merged = _merge([spans_a, spans_b])
    assert len(merged) == 1
    assert merged[0].confidence == pytest.approx(0.95)


def test_merge_keeps_non_overlapping_from_both_models():
    spans_a = [make_span("量子纠错", EntityType.TECH, 0, 4, 0.90)]
    spans_b = [make_span("中国科学院", EntityType.ORG, 5, 10, 0.85)]
    merged = _merge([spans_a, spans_b])
    assert len(merged) == 2


def test_remove_overlaps_keeps_higher_confidence():
    spans = [
        make_span("量子纠错码", EntityType.TECH, 0, 5, 0.90),
        make_span("量子", EntityType.TECH, 0, 2, 0.70),  # 重叠，低分
    ]
    result = _remove_overlaps(spans)
    assert len(result) == 1
    assert result[0].text == "量子纠错码"


def test_remove_overlaps_keeps_non_overlapping():
    spans = [
        make_span("量子纠错", EntityType.TECH, 0, 4, 0.90),
        make_span("中科院", EntityType.ORG, 6, 9, 0.85),
    ]
    result = _remove_overlaps(spans)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_ensemble_confidence_filter():
    bert = AsyncMock(spec=BertCRFNER)
    bert.predict = AsyncMock(return_value=[
        make_span("量子纠错", EntityType.TECH, 0, 4, 0.50),   # 低于阈值
        make_span("中科院", EntityType.ORG, 5, 8, 0.85),
    ])
    ensemble = EnsembleNER(bert_crf=bert, uie=None, min_confidence=0.7)
    spans = await ensemble.predict("量子纠错中科院")
    assert len(spans) == 1
    assert spans[0].label == EntityType.ORG


@pytest.mark.asyncio
async def test_ensemble_model_failure_degrades_gracefully():
    bert = AsyncMock(spec=BertCRFNER)
    bert.predict = AsyncMock(side_effect=ConnectionError("service down"))

    uie = AsyncMock(spec=UIENER)
    uie.predict = AsyncMock(return_value=[
        make_span("量子计算", EntityType.TECH, 0, 4, 0.88)
    ])

    ensemble = EnsembleNER(bert_crf=bert, uie=uie, min_confidence=0.7)
    spans = await ensemble.predict("量子计算")
    # BERT-CRF 失败，UIE 结果仍返回
    assert len(spans) == 1
    assert spans[0].text == "量子计算"


@pytest.mark.asyncio
async def test_ensemble_no_models_returns_empty():
    ensemble = EnsembleNER(bert_crf=None, uie=None)
    spans = await ensemble.predict("任意文本")
    assert spans == []
