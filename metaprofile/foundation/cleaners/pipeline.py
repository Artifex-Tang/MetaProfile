"""
清洗管道编排。

链路：RawDocument → dedup → normalize → validate → CleanedDocument

输出 CleanedDocument 给下游 NER / Extractor。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import structlog

from metaprofile.foundation.cleaners.deduplicator import Deduplicator
from metaprofile.foundation.cleaners.normalizer import NormalizedDoc, normalize
from metaprofile.foundation.cleaners.validator import (
    ValidateOutcome,
    ValidationResult,
    validate,
)
from metaprofile.foundation.collectors.base import RawDocument

logger = structlog.get_logger(__name__)


@dataclass
class CleanedDocument:
    """清洗完成、可入库的文档。"""

    source: str
    doc_type: str
    raw_id: str
    url: str | None
    lang: str
    fields: dict[str, Any]
    completeness: float
    warnings: list[str]   # DEGRADE 时记录缺失的推荐字段


@dataclass
class PipelineStats:
    total: int = 0
    deduped: int = 0
    rejected: int = 0
    degraded: int = 0
    passed: int = 0

    @property
    def accepted(self) -> int:
        return self.passed + self.degraded


class CleaningPipeline:
    """
    单批次清洗管道（无状态，可复用）。

    用法：
        pipeline = CleaningPipeline()
        docs, stats = await pipeline.run(raw_docs)
    """

    def __init__(self, deduplicator: Deduplicator | None = None) -> None:
        self._dedup = deduplicator or Deduplicator()

    def run_sync(
        self, raw_docs: list[RawDocument]
    ) -> tuple[list[CleanedDocument], PipelineStats]:
        """同步版本（供测试和脚本使用）。"""
        stats = PipelineStats(total=len(raw_docs))

        # 去重
        unique, dropped = self._dedup.dedup(raw_docs)
        stats.deduped = dropped

        cleaned: list[CleanedDocument] = []
        for raw in unique:
            result = self._process_one(raw)
            if result is None:
                stats.rejected += 1
                continue
            if result.outcome == ValidateOutcome.DEGRADE:
                stats.degraded += 1
            else:
                stats.passed += 1
            cleaned.append(_to_cleaned(result))

        logger.info(
            "pipeline_done",
            total=stats.total,
            accepted=stats.accepted,
            deduped=stats.deduped,
            rejected=stats.rejected,
        )
        return cleaned, stats

    async def run(
        self, raw_docs: list[RawDocument]
    ) -> tuple[list[CleanedDocument], PipelineStats]:
        """异步版本（供生产 worker 使用，实际处理是 CPU-bound 故直接调同步）。"""
        return self.run_sync(raw_docs)

    async def stream(
        self, raw_stream: AsyncIterator[RawDocument], batch_size: int = 100
    ) -> AsyncIterator[tuple[list[CleanedDocument], PipelineStats]]:
        """流式处理：按 batch_size 聚合后清洗，yield (batch_cleaned, stats)。"""
        batch: list[RawDocument] = []
        async for doc in raw_stream:
            batch.append(doc)
            if len(batch) >= batch_size:
                yield await self.run(batch)
                batch = []
        if batch:
            yield await self.run(batch)

    def _process_one(self, raw: RawDocument) -> ValidationResult | None:
        try:
            normed: NormalizedDoc = normalize(raw)
            result: ValidationResult = validate(normed)
            if result.outcome == ValidateOutcome.REJECT:
                return None
            return result
        except Exception as exc:
            logger.warning(
                "pipeline_process_error",
                source=raw.source,
                raw_id=raw.raw_id,
                error=str(exc),
            )
            return None


def _to_cleaned(result: ValidationResult) -> CleanedDocument:
    return CleanedDocument(
        source=result.doc.source,
        doc_type=result.doc.doc_type,
        raw_id=result.doc.raw_id,
        url=result.doc.url,
        lang=result.doc.lang,
        fields=result.doc.fields,
        completeness=result.completeness,
        warnings=[f"missing_recommended: {f}" for f in result.missing_recommended],
    )
