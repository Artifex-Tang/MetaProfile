"""机构属性抽取器。"""
from __future__ import annotations

from metaprofile.foundation.extractors.base import AbstractExtractor
from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.schemas.entity_org import OrgExtractionResult

SYSTEM_PROMPT = """你是产业技术情报分析专家。从文本中抽取机构实体属性。
要求：
1. 严格遵循输出 schema。
2. 必填：机构中文名称、外文名称、国家、机构简介、机构类型、机构性质、机构职能、技术领域、运行年数。
3. 机构类型从枚举中选择：管理机构/科研机构/高校/企业/咨询机构/试验鉴定机构/其他。
4. 找不到的字段保持为空，不要编造。
"""


class OrgExtractor(AbstractExtractor[OrgExtractionResult]):
    caller_name = "org_extractor"

    async def extract(
        self, text: str, *, source_doc_id: str | None = None
    ) -> OrgExtractionResult:
        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.extraction_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=f"请从以下文本中抽取机构属性：\n\n{text}",
            function_name="extract_org_profile",
            function_description="从文本中抽取机构实体的画像属性，遵循《实体画像数据规范》机构节",
            output_schema=OrgExtractionResult,
            caller=self.caller_name,
        )
        return result
