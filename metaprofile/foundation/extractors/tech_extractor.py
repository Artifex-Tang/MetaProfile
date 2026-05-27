"""
技术实体属性抽取器。

输入：NER 识别出的技术实体 + 上下文（前后 500 字）。
输出：TechExtractionResult（必填字段 + 部分可选字段）。

LLM 调用方式：Function Calling，schema 来自 TechExtractionResult。
"""
from __future__ import annotations

import structlog

from metaprofile.foundation.extractors.base import AbstractExtractor
from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.schemas.entity_tech import TechExtractionResult

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """你是产业技术情报分析专家。从给定文本中抽取技术实体的属性。
要求：
1. 严格遵循输出 schema，不得生成 schema 之外的字段。
2. 中文名称、英文名称、所属技术领域、技术简介、发展现状、发展趋势 6 项必填。
3. 发展现状与发展趋势按 "观点1：...；观点2：...；观点3：..." 格式归纳。
4. 关键技术点输出为短语列表，每条不超过 20 字。
5. 置信度 confidence 反映你对抽取结果的整体把握度（0.0~1.0）。
6. 找不到的字段保持为空，不要编造。
"""


class TechExtractor(AbstractExtractor[TechExtractionResult]):
    caller_name = "tech_extractor"

    async def extract(
        self, text: str, *, source_doc_id: str | None = None
    ) -> TechExtractionResult:
        user_prompt = f"""请从以下文本中抽取技术属性：

{text}

请调用 extract_tech_profile 函数返回结构化结果。"""

        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.extraction_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            function_name="extract_tech_profile",
            function_description="从文本中抽取技术实体的画像属性，遵循《实体画像数据规范》技术节",
            output_schema=TechExtractionResult,
            caller=self.caller_name,
        )

        logger.info(
            "tech_extracted",
            tech_name=result.tech_name_cn,
            confidence=result.confidence,
            source_doc_id=source_doc_id,
        )
        return result
