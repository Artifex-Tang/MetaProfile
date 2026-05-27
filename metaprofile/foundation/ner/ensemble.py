"""
NER 多模型集成。

策略：
1. 并行调用 BERT-CRF 和 UIE
2. 相同 span（文本+标签一致）取置信度最高者
3. 不重叠的 span 合并（按 start 排序，贪心去重叠）
4. 按 confidence >= min_confidence 阈值过滤
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from metaprofile.foundation.ner.bert_crf import BertCRFNER, NERSpan
from metaprofile.foundation.ner.uie import UIENER
from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import EntityType

logger = structlog.get_logger(__name__)


class EnsembleNER:
    """
    BERT-CRF + UIE 集成 NER。

    两个模型均可用时并行调用；任一不可用时自动降级为单模型。
    """

    def __init__(
        self,
        bert_crf: BertCRFNER | None = None,
        uie: UIENER | None = None,
        min_confidence: float | None = None,
    ) -> None:
        self._bert = bert_crf
        self._uie = uie
        self._min_conf = min_confidence or settings.thresholds.ner_confidence_min

    async def predict(self, text: str) -> list[NERSpan]:
        """并行推理，集成结果后返回去重、去重叠、过阈值的 span 列表。"""
        tasks: list[Any] = []
        if self._bert:
            tasks.append(self._safe_predict(self._bert, text, "bert_crf"))
        if self._uie:
            tasks.append(self._safe_predict(self._uie, text, "uie"))

        if not tasks:
            return []

        results: list[list[NERSpan]] = await asyncio.gather(*tasks)
        merged = _merge(results)
        filtered = [s for s in merged if s.confidence >= self._min_conf]

        logger.info(
            "ensemble_ner_done",
            text_len=len(text),
            raw_count=sum(len(r) for r in results),
            after_merge=len(merged),
            after_filter=len(filtered),
        )
        return filtered

    async def predict_batch(self, texts: list[str]) -> list[list[NERSpan]]:
        return [await self.predict(t) for t in texts]

    @staticmethod
    async def _safe_predict(
        model: BertCRFNER | UIENER,
        text: str,
        name: str,
    ) -> list[NERSpan]:
        try:
            return await model.predict(text)
        except Exception as exc:
            logger.warning("ensemble_model_failed", model=name, error=str(exc))
            return []


# ─── 集成算法 ────────────────────────────────────────────────────────────────

def _merge(result_sets: list[list[NERSpan]]) -> list[NERSpan]:
    """合并多模型输出，同 span 保留最高置信度，然后去重叠。"""
    # Key: (text, label) → best confidence span
    best: dict[tuple[str, EntityType], NERSpan] = {}

    for spans in result_sets:
        for span in spans:
            key = (span.text, span.label)
            existing = best.get(key)
            if existing is None or span.confidence > existing.confidence:
                best[key] = span

    candidates = sorted(best.values(), key=lambda s: s.start)
    return _remove_overlaps(candidates)


def _remove_overlaps(spans: list[NERSpan]) -> list[NERSpan]:
    """贪心去重叠：保留置信度高的 span，与其重叠的低分 span 丢弃。"""
    # 先按置信度降序，再按 start 排序
    by_conf = sorted(spans, key=lambda s: (-s.confidence, s.start))
    kept: list[NERSpan] = []
    occupied: list[tuple[int, int]] = []  # (start, end)

    for span in by_conf:
        overlap = any(
            not (span.end <= s or span.start >= e)
            for s, e in occupied
        )
        if not overlap:
            kept.append(span)
            occupied.append((span.start, span.end))

    return sorted(kept, key=lambda s: s.start)
