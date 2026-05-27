"""
补全流水线。

完整度评分 → 触发阈值判断 → RAG 检索 → LLM 字段补全 → 写回存储。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from metaprofile.foundation.enrichment.completeness import CompletenessResult, score_completeness
from metaprofile.foundation.enrichment.llm_filler import FillResult, LLMFieldFiller
from metaprofile.foundation.enrichment.rag_retriever import RAGRetriever, RetrievedDoc
from metaprofile.shared.schemas.base import EntityType

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    entity_id: str
    entity_type: EntityType
    completeness_before: float
    completeness_after: float
    filled_fields: list[str]
    skipped: bool = False           # True = above threshold, no enrichment needed
    error: str | None = None


class EnrichmentPipeline:
    """
    端到端补全流水线。

    Args:
        retriever: RAGRetriever
        filler: LLMFieldFiller
        unified_repo: UnifiedRepo（读写实体）
    """

    def __init__(
        self,
        retriever: RAGRetriever,
        filler: LLMFieldFiller,
        unified_repo: Any,
    ) -> None:
        self._retriever = retriever
        self._filler = filler
        self._repo = unified_repo

    async def enrich(
        self,
        *,
        entity_type: EntityType,
        entity_id: str,
    ) -> EnrichmentResult:
        """
        对单个实体执行补全。

        Returns:
            EnrichmentResult with before/after completeness and filled fields.
        """
        attrs = await self._repo.get_entity(entity_type, entity_id)
        if attrs is None:
            return EnrichmentResult(
                entity_id=entity_id,
                entity_type=entity_type,
                completeness_before=0.0,
                completeness_after=0.0,
                filled_fields=[],
                error="entity_not_found",
            )

        before = score_completeness(entity_type, attrs)

        if not before.needs_enrichment:
            return EnrichmentResult(
                entity_id=entity_id,
                entity_type=entity_type,
                completeness_before=before.score,
                completeness_after=before.score,
                filled_fields=[],
                skipped=True,
            )

        query_text = _build_query(entity_type, attrs)
        docs = await self._retriever.retrieve(
            entity_type=entity_type,
            query_text=query_text,
        )
        snippets = [f"{d.title}\n{d.snippet}" for d in docs]

        fill_result = await self._filler.fill(
            entity_type=entity_type,
            entity_attrs=attrs,
            missing_fields=before.missing_fields,
            context_docs=snippets,
        )

        if fill_result.filled_fields:
            merged = {**attrs, **fill_result.filled_fields}
            await self._repo.upsert_entity(entity_type, entity_id, merged)
            after = score_completeness(entity_type, merged)
        else:
            after = before

        logger.info(
            "enrichment done",
            extra={
                "entity_id": entity_id,
                "entity_type": entity_type,
                "before": before.score,
                "after": after.score,
                "filled": fill_result.accepted_fields,
            },
        )

        return EnrichmentResult(
            entity_id=entity_id,
            entity_type=entity_type,
            completeness_before=before.score,
            completeness_after=after.score,
            filled_fields=fill_result.accepted_fields,
        )

    async def enrich_batch(
        self,
        items: list[tuple[EntityType, str]],
    ) -> list[EnrichmentResult]:
        """批量补全，逐条执行（LLM 串行避免超速限）。"""
        results = []
        for entity_type, entity_id in items:
            result = await self.enrich(entity_type=entity_type, entity_id=entity_id)
            results.append(result)
        return results


# ─── helpers ────────────────────────────────────────────────────────────────

_NAME_FIELDS: dict[EntityType, list[str]] = {
    EntityType.TECH: ["tech_name_cn", "tech_name_en", "tech_summary"],
    EntityType.ORG: ["name_cn", "name_en", "summary"],
    EntityType.PERSON: ["name_cn", "name_en", "summary"],
    EntityType.PROJECT: ["project_name", "summary"],
}


def _build_query(entity_type: EntityType, attrs: dict[str, Any]) -> str:
    parts = []
    for f in _NAME_FIELDS.get(entity_type, []):
        v = attrs.get(f)
        if v and isinstance(v, str):
            parts.append(v)
    return " ".join(parts)[:500]
