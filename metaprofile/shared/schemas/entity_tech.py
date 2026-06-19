"""
技术实体画像数据模型。

字段定义严格遵循《实体画像数据规范》技术节，**禁止**新增/删除/修改字段。
本模型既用于 LLM Function Calling 的 schema，也用于 API 请求/响应。
"""
from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator

from metaprofile.shared.schemas.base import EntityRef, ProfileBase, ReviewType


def _coerce_json_list(v):
    """容 ingest 稀疏数据：ODS keyword 等字段在 ORM JSON 列里可能存成
    JSON-encoded 字符串(如 '["a","b"]')，读回时 pydantic list[str] 拒绝。
    这里把"看起来是 JSON 数组的字符串"解析回 list。"""
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("[") and s.endswith("]"):
            import json
            try:
                parsed = json.loads(s)
            except (ValueError, TypeError):
                return v
            if isinstance(parsed, list):
                return parsed
    return v


# ─────────────────────────── 扩展属性 ────────────────────────────
class TechDevMilestone(ProfileBase):
    """技术发展进程（里程碑事件）。"""

    milestone_date: date | None = Field(default=None, description="里程碑事件时间")
    milestone_name: str | None = Field(default=None, description="里程碑事件名称")
    contributor_keywords: list[str] = Field(
        default_factory=list, description="贡献主体关键词（机构/人员/企业名称）"
    )
    milestone_content: str | None = Field(default=None, description="里程碑事件内容")


class TechReviewImpact(ProfileBase):
    """评议及影响。"""

    review_date: date | None = None
    review_org: str | None = Field(default=None, description="评议机构")
    review_person: str | None = Field(default=None, description="评议人员")
    review_content: str | None = None
    review_type: ReviewType | None = None


class TechFunding(ProfileBase):
    """经费投入。"""

    amount: float | None = Field(default=None, description="投入经费")
    source: str | None = Field(default=None, description="经费来源")


class TechAcademicOutput(ProfileBase):
    """学术成果。"""

    name: str | None = Field(default=None, description="成果名称")
    publish_date: date | None = None
    subject_keywords: list[str] = Field(
        default_factory=list, description="成果主体（机构/人员）"
    )
    image: str | None = Field(default=None, description="成果图片文件名")


class TechExperiment(ProfileBase):
    """科研实验。"""

    content: str | None = Field(default=None, description="实验内容")
    experiment_date: date | None = None
    result: str | None = Field(default=None, description="实验结果")
    subject_keywords: list[str] = Field(
        default_factory=list, description="实验主体（机构/人员/项目/事件）"
    )
    image: str | None = None


# ─────────────────────────── 主画像 ────────────────────────────
class TechProfile(ProfileBase):
    """技术画像（基本属性 + 扩展属性）。

    与数据规范字段一一对应，命名遵循驼峰式中文语义但保留英文以便序列化。
    必填项严格遵循数据规范：技术中文/外文名称、所属技术领域、技术简介、发展现状、发展趋势。
    """

    # ── 基本属性 ──
    tech_id: str | None = Field(
        default=None, description="技术唯一标识（系统生成，新建时可省略）"
    )
    tech_name_cn: str = Field(default="", description="技术中文名称")
    tech_name_en: str = Field(default="", description="技术外文名称")
    tech_name_other: str | None = Field(default=None, description="技术其他名称")
    tech_domain: list[str] = Field(
        default_factory=list, description="所属技术领域（允许多值）"
    )
    invention_date: date | None = Field(default=None, description="发明时间")
    application_date: date | None = Field(default=None, description="应用时间")
    tech_summary: str = Field(..., description="技术简介（必填，包括原理、内涵）")
    dev_goal: str | None = Field(default=None, description="发展目标")
    project_layout: list[str] = Field(default_factory=list, description="项目布局")
    key_points: list[str] = Field(default_factory=list, description="关键技术点")

    @field_validator("key_points", mode="before")
    @classmethod
    def _coerce_key_points(cls, v):
        return _coerce_json_list(v)
    transformation_status: str | None = Field(
        default=None, description="转化应用情况"
    )
    basic_research_status: str | None = Field(
        default=None, description="基础研究情况"
    )
    autonomy_capability: str | None = Field(
        default=None, description="技术自主可控能力"
    )
    industrial_capability: str | None = Field(
        default=None, description="工业生产能力"
    )
    tech_advantages: str | None = Field(default=None, description="技术优势")
    current_status: str = Field(
        ..., description="发展现状（必填，按观点1、2、3填写）"
    )
    trend: str = Field(..., description="发展趋势（必填，按观点1、2、3填写）")
    remark: str | None = Field(default=None, description="备注")

    # ── 扩展属性 ──
    dev_milestones: list[TechDevMilestone] = Field(default_factory=list)
    review_impacts: list[TechReviewImpact] = Field(default_factory=list)
    funding: list[TechFunding] = Field(default_factory=list)
    academic_outputs: list[TechAcademicOutput] = Field(default_factory=list)
    experiments: list[TechExperiment] = Field(default_factory=list)

    # ── 关系（贡献者 / 被评议） ──
    contributor_orgs: list[EntityRef] = Field(default_factory=list)
    contributor_persons: list[EntityRef] = Field(default_factory=list)
    contributor_enterprises: list[EntityRef] = Field(default_factory=list)
    reviewed_by_orgs: list[EntityRef] = Field(default_factory=list)
    reviewed_by_persons: list[EntityRef] = Field(default_factory=list)
    reviewed_by_enterprises: list[EntityRef] = Field(default_factory=list)

    # ── 抽取元数据 ──
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TechExtractionResult(ProfileBase):
    """LLM Function Calling 专用：技术属性抽取结果。

    字段是 TechProfile 的必填子集 + 关键可选字段，避免 LLM 一次输出过大 schema。
    """

    tech_name_cn: str
    tech_name_en: str | None = None
    tech_domain: list[str]
    tech_summary: str
    dev_goal: str | None = None
    key_points: list[str] = Field(default_factory=list)
    current_status: str
    trend: str
    invention_date: date | None = None
    application_date: date | None = None
    autonomy_capability: str | None = None
    tech_advantages: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
