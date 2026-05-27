"""
NER Span → LLM Function Calling 抽取编排器。

职责：
1. 接收 NER 识别出的实体 span + 原始文档文本
2. 为每个 span 截取上下文窗口（span ± CONTEXT_CHARS）
3. 按实体类型分发到对应的 AbstractExtractor 子类
4. 返回抽取结果列表（含置信度和溯源信息）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from metaprofile.foundation.extractors.base import AbstractExtractor
from metaprofile.foundation.extractors.org_extractor import OrgExtractor
from metaprofile.foundation.extractors.person_extractor import PersonExtractor
from metaprofile.foundation.extractors.project_extractor import ProjectExtractor
from metaprofile.foundation.extractors.tech_extractor import TechExtractor
from metaprofile.foundation.ner.bert_crf import NERSpan
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.utils.text_normalizer import truncate_text

logger = structlog.get_logger(__name__)

CONTEXT_CHARS = 500   # span 两侧各取 500 字符作为上下文
MAX_TEXT_CHARS = 2000  # 送入 LLM 的最大字符数


@dataclass
class ExtractionJob:
    span: NERSpan
    context_text: str
    source_doc_id: str | None = None


@dataclass
class ExtractionOutput:
    entity_type: EntityType
    span_text: str
    result: Any          # 对应 TechExtractionResult / OrgExtractionResult 等
    source_doc_id: str | None


class LLMFunctionExtractor:
    """NER → LLM Function Calling 批量抽取器。"""

    def __init__(self, gateway: LLMGateway) -> None:
        self._extractors: dict[EntityType, AbstractExtractor] = {
            EntityType.TECH: TechExtractor(gateway),
            EntityType.ORG: OrgExtractor(gateway),
            EntityType.PERSON: PersonExtractor(gateway),
            EntityType.PROJECT: ProjectExtractor(gateway),
        }

    async def extract_from_spans(
        self,
        *,
        text: str,
        spans: list[NERSpan],
        source_doc_id: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[ExtractionOutput]:
        """
        对 spans 中的每个 NER 结果调用对应的 LLM 抽取器。

        Args:
            text: 原始文档全文（用于切取上下文窗口）
            spans: NER 输出的实体 span 列表
            source_doc_id: 溯源文档 ID
            min_confidence: NER 置信度过滤阈值

        Returns:
            ExtractionOutput 列表
        """
        filtered = [s for s in spans if s.confidence >= min_confidence]
        outputs: list[ExtractionOutput] = []

        for span in filtered:
            extractor = self._extractors.get(span.label)
            if extractor is None:
                continue

            context = _build_context(text, span)
            try:
                result = await extractor.extract(context, source_doc_id=source_doc_id)
                outputs.append(
                    ExtractionOutput(
                        entity_type=span.label,
                        span_text=span.text,
                        result=result,
                        source_doc_id=source_doc_id,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "llm_extraction_failed",
                    span=span.text,
                    entity_type=span.label,
                    error=str(exc),
                )

        logger.info(
            "llm_function_extract_done",
            input_spans=len(filtered),
            outputs=len(outputs),
            source_doc_id=source_doc_id,
        )
        return outputs


def _build_context(text: str, span: NERSpan) -> str:
    """从原始文本中截取 span 的上下文窗口。"""
    start = max(0, span.start - CONTEXT_CHARS)
    end = min(len(text), span.end + CONTEXT_CHARS)
    window = text[start:end]
    return truncate_text(window, MAX_TEXT_CHARS)
