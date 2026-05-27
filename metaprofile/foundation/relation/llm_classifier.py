"""
LLM 关系分类器。

输入：主实体、客实体、原文证据片段
输出：RelationType 枚举值 + 置信度

仅在规则抽取器无法确定关系类型时调用（节省 Token）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import EntityType, ProfileBase, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple, RelationType

_ALL_RELATION_VALUES = [r.value for r in RelationType]

SYSTEM_PROMPT = """你是知识图谱关系分类专家。
根据提供的文本证据，判断主实体和客实体之间的关系类型。
关系类型必须从给定枚举中选择，不可自造。
若无明确关系证据，请返回 confidence < 0.5。
"""


class _RelationOutput(ProfileBase):
    relation_value: str = Field(
        ...,
        description=f"关系类型，必须是以下之一：{_ALL_RELATION_VALUES}",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., description="判定依据（一句话）")


class LLMRelationClassifier:
    caller_name = "llm_relation_classifier"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def classify(
        self,
        *,
        subject_id: str,
        subject_type: EntityType,
        subject_name: str,
        object_id: str,
        object_type: EntityType,
        object_name: str,
        evidence: str,
        source_doc_id: str | None = None,
        min_confidence: float = 0.6,
    ) -> RelationTriple | None:
        """
        LLM 判定两个实体间关系。

        Returns:
            RelationTriple（含置信度）；置信度 < min_confidence 时返回 None
        """
        user_prompt = (
            f"主实体：{subject_name}（类型：{subject_type.value}）\n"
            f"客实体：{object_name}（类型：{object_type.value}）\n\n"
            f"证据文本：\n{evidence}\n\n"
            f"请调用 classify_relation 函数，返回关系类型。"
        )

        try:
            result, _ = await call_with_schema(
                gateway=self._gateway,
                model=settings.llm.judge_model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                function_name="classify_relation",
                function_description="判定两个实体之间的关系类型",
                output_schema=_RelationOutput,
                caller=self.caller_name,
            )
        except Exception:  # noqa: BLE001
            return None

        if result.confidence < min_confidence:
            return None

        try:
            relation = RelationType(result.relation_value)
        except ValueError:
            return None

        return RelationTriple(
            subject_id=subject_id,
            subject_type=subject_type,
            subject_name=subject_name,
            relation=relation,
            object_id=object_id,
            object_type=object_type,
            object_name=object_name,
            evidence=evidence,
            confidence=result.confidence,
            source_doc_id=source_doc_id,
            method=SourceMethod.LLM_EXTRACT,
            extracted_at=datetime.now(timezone.utc),
        )
