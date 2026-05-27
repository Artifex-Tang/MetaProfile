"""项目属性抽取器。"""
from __future__ import annotations

from metaprofile.foundation.extractors.base import AbstractExtractor
from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.schemas.entity_project import ProjectExtractionResult

SYSTEM_PROMPT = """你是产业科技项目分析专家。从文本中抽取科研项目属性。
要求：
1. 严格遵循输出 schema。
2. 必填：项目中文名称、英文名称、技术领域、启动时间、项目编号、主管机构、主要研究内容、主要进展。
3. 启动时间标准化为 yyyy-MM-dd（仅有年份时填 yyyy-01-01）。
4. 找不到的字段保持为空，不要编造。
"""


class ProjectExtractor(AbstractExtractor[ProjectExtractionResult]):
    caller_name = "project_extractor"

    async def extract(
        self, text: str, *, source_doc_id: str | None = None
    ) -> ProjectExtractionResult:
        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.extraction_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=f"请从以下文本中抽取项目属性：\n\n{text}",
            function_name="extract_project_profile",
            function_description="从文本中抽取科研项目的画像属性，遵循《实体画像数据规范》项目节",
            output_schema=ProjectExtractionResult,
            caller=self.caller_name,
        )
        return result
