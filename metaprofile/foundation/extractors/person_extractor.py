"""人员属性抽取器。"""
from __future__ import annotations

from metaprofile.foundation.extractors.base import AbstractExtractor
from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.schemas.entity_person import PersonExtractionResult

SYSTEM_PROMPT = """你是产业科技人才分析专家。从文本中抽取产业重点人物属性。
要求：
1. 严格遵循输出 schema。
2. 必填：人员中文姓名、外文姓名、性别、国籍、人员简介、当前职务/职位、专业领域。
3. 性别从 男/女 中选；最高学历从 本科/硕士/博士 中选。
4. 找不到的字段保持为空，不要编造。
5. 涉及隐私敏感字段（出生日期、出生地等），仅当文本中明确出现时才填。
"""


class PersonExtractor(AbstractExtractor[PersonExtractionResult]):
    caller_name = "person_extractor"

    async def extract(
        self, text: str, *, source_doc_id: str | None = None
    ) -> PersonExtractionResult:
        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.extraction_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=f"请从以下文本中抽取人员属性：\n\n{text}",
            function_name="extract_person_profile",
            function_description="从文本中抽取产业重点人物的画像属性，遵循《实体画像数据规范》人员节",
            output_schema=PersonExtractionResult,
            caller=self.caller_name,
        )
        return result
