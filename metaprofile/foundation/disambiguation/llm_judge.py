"""
LLM 实体消歧精判。

候选对来自 candidate_recall（Embedding 相似度 0.70~0.95），
通过 LLM 判定是否为同一实体。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import EntityType, ProfileBase


class DisambiguationVerdict(ProfileBase):
    """LLM 同一性判定输出。"""

    is_same: bool
    reason: str = Field(..., description="判定依据")
    merge_to: str = Field(
        ..., description="若是同一实体，保留哪个 entity_id 作为主记录"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)


SYSTEM_PROMPT = """你是实体识别专家。判断两个实体是否为同一实体。
判定依据：名称（含别名/简称/外文名）、机构类型、地址、领域、成立/出生时间等。
注意机构更名场景（如 XX 研究所 → XX 研究院 是同一实体）；
注意人物多语言姓名场景（John Smith / 约翰·史密斯 是同一实体）；
注意企业集团与子公司是不同实体。
"""


class LLMDisambiguator:
    caller_name = "llm_disambiguator"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def judge(
        self,
        *,
        entity_type: EntityType,
        entity_a: dict[str, Any],
        entity_b: dict[str, Any],
    ) -> DisambiguationVerdict:
        user_prompt = f"""判定以下两个 {entity_type.value} 实体是否为同一实体：

实体A：
{self._format_entity(entity_a)}

实体B：
{self._format_entity(entity_b)}

请调用 disambiguate 函数返回判定结果。
"""
        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.judge_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            function_name="disambiguate",
            function_description="判定两个实体是否为同一实体",
            output_schema=DisambiguationVerdict,
            caller=self.caller_name,
        )
        return result

    @staticmethod
    def _format_entity(entity: dict[str, Any]) -> str:
        lines = []
        for k, v in entity.items():
            if v is None or v == "" or v == []:
                continue
            if isinstance(v, datetime):
                v = v.isoformat()
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)
