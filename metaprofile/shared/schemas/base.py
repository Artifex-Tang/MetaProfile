"""画像 Pydantic 基类与公共枚举。"""
from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EntityType(StrEnum):
    """四类实体类型（与 NER 标签对应）。"""

    TECH = "TECH"
    PROJECT = "PROJECT"
    ORG = "ORG"
    PERSON = "PERSON"

    # 卫星实体(关系端点,非画像类型):为全 48 关系进图做铺垫,
    # Neo4j label/前端 TYPE_META/_PREDICATE_MAP 由后续任务补。
    # value 用 ASCII(同上 4 类),因 .value 是 load-bearing 标识符(id_generator
    # ID 前缀/postgres entity_type 列/es 索引名);中文展示名走前端 TYPE_META/label 图。
    STRATEGY = "STRATEGY"
    EVENT = "EVENT"
    ENTERPRISE = "ENTERPRISE"
    CONTRACT = "CONTRACT"
    PACKAGE = "PACKAGE"


class SourceMethod(StrEnum):
    """字段抽取来源：用于审计追溯。"""

    RULE = "rule"
    LLM_EXTRACT = "llm_extract"
    LLM_ENRICH = "llm_enrich"
    HUMAN = "human"


class ReviewType(StrEnum):
    POSITIVE = "正面信息"
    NEGATIVE = "负面信息"
    OTHER = "其他"


class ProfileBase(BaseModel):
    """所有画像 Pydantic 基类。"""

    model_config = ConfigDict(
        extra="forbid",  # 禁止额外字段，防止规范漂移
        str_strip_whitespace=True,
        populate_by_name=True,
        from_attributes=True,
    )


class FieldProvenance(ProfileBase):
    """字段级溯源信息：每个 LLM 抽取/补全字段都需记录。"""

    field: str
    method: SourceMethod
    source_doc_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    extracted_at: datetime


class EntityRef(ProfileBase):
    """实体引用（用于关系字段）。"""

    entity_id: str
    entity_type: EntityType
    name: str | None = None
