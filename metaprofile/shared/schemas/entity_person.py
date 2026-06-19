"""
人员实体画像数据模型。字段严格遵循《实体画像数据规范》人员节。
"""
from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from metaprofile.shared.schemas.base import EntityRef, ProfileBase, ReviewType


class Gender(StrEnum):
    MALE = "男"
    FEMALE = "女"


class Degree(StrEnum):
    BACHELOR = "本科"
    MASTER = "硕士"
    DOCTOR = "博士"


class PersonCategory(StrEnum):
    MANAGEMENT = "管理"
    RESEARCH = "研究"
    OTHER = "其他"


class AcademicForm(StrEnum):
    PAPER = "论文"
    BOOK = "专著"
    PATENT = "专利"
    REPORT = "汇报文稿"


class AuthorRank(StrEnum):
    SOLE = "独著"
    FIRST = "第一作者"
    SECOND = "第二作者"
    THIRD = "第三作者"
    OTHER = "其他"


class PersonEducation(ProfileBase):
    """教育经历。"""

    start_date: date | None = None
    degree_date: date | None = None
    degree: Degree | None = None
    school: str | None = None
    major: str | None = None


class PersonCareer(ProfileBase):
    """工作经历。"""

    start_date: date = Field(..., description="任职开始时间（必填）")
    end_date: date | None = None
    org: str = Field(..., description="任职机构（必填）")
    enterprise: str | None = None
    military_unit: str | None = None
    position: str | None = None


class PersonAward(ProfileBase):
    """荣誉奖励。"""

    description: str | None = Field(
        default=None, description="奖励名称、获奖时间、获奖原因、颁发机构"
    )


class PersonAcademicOutput(ProfileBase):
    """主要学术成果。"""

    name: str | None = None
    form: AcademicForm | None = None
    publish_date: date | None = None
    rank: AuthorRank | None = None
    tech_domain: str | None = None
    collaborators: list[str] = Field(default_factory=list)
    citations: int | None = None
    is_representative: bool | None = None


class PersonOpinion(ProfileBase):
    """观点言论。"""

    title: str = Field(..., description="观点言论标题（必填）")
    publish_date: date = Field(..., description="发表时间（必填）")
    raw_text: str = Field(..., description="观点言论原文（必填）")
    occasion: str | None = None
    main_points: str | None = None
    target_keywords: list[str] = Field(default_factory=list)


class PersonReview(ProfileBase):
    """社会评议及影响。"""

    content: str | None = None
    review_org: str | None = None
    review_enterprise: str | None = None
    review_person: str | None = None
    review_type: ReviewType | None = None
    review_date: date | None = None


class PersonFocus(ProfileBase):
    """技术关注重点。"""

    content: list[str] = Field(default_factory=list)
    consistency_with_policy: str | None = None
    potential_impact: list[str] = Field(default_factory=list)


class PersonReformFocus(ProfileBase):
    """政策改革重点。"""

    content: list[str] = Field(default_factory=list)
    consistency_with_policy: str | None = None
    potential_impact: list[str] = Field(default_factory=list)


class PersonProfile(ProfileBase):
    """人员画像。"""

    # ── 基本属性 ──
    person_id: str | None = None
    name_cn: str = Field(default="", description="人员中文姓名")
    name_en: str = Field(default="", description="人员外文姓名")
    gender: Gender = Field(..., description="性别（必填）")
    avatar: list[str] = Field(default_factory=list)
    nationality: str = Field(..., description="国籍（必填）")
    summary: str = Field(..., description="人员简介（必填）")
    birth_date: date | None = None
    age: int | None = None
    birthplace: str | None = None
    ethnicity: str | None = None
    current_residence: str | None = None
    current_org: str | None = None
    current_enterprise: str | None = None
    current_military_unit: str | None = None
    current_position: list[str] = Field(
        ..., min_length=1, description="当前职务/职位（必填）"
    )
    highest_degree: Degree | None = None
    person_category: PersonCategory | None = None
    professional_domains: list[str] = Field(
        ..., min_length=1, description="专业领域（必填）"
    )
    professional_skills: list[str] = Field(default_factory=list)
    social_media: str | None = None
    personality_traits: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)
    management_philosophy: list[str] = Field(default_factory=list)
    remark: list[str] = Field(default_factory=list)

    # ── 扩展属性 ──
    educations: list[PersonEducation] = Field(default_factory=list)
    careers: list[PersonCareer] = Field(default_factory=list)
    awards: list[PersonAward] = Field(default_factory=list)
    academic_outputs: list[PersonAcademicOutput] = Field(default_factory=list)
    opinions: list[PersonOpinion] = Field(default_factory=list)
    reviews: list[PersonReview] = Field(default_factory=list)
    tech_focuses: list[PersonFocus] = Field(default_factory=list)
    reform_focuses: list[PersonReformFocus] = Field(default_factory=list)

    # ── 关系 ──
    affiliated_orgs: list[EntityRef] = Field(default_factory=list)
    evaluated_orgs: list[EntityRef] = Field(default_factory=list)
    drafted_strategies: list[EntityRef] = Field(default_factory=list)
    managed_projects: list[EntityRef] = Field(default_factory=list)
    researched_projects: list[EntityRef] = Field(default_factory=list)
    cooperated_persons: list[EntityRef] = Field(default_factory=list)
    superior_persons: list[EntityRef] = Field(default_factory=list)
    subordinate_persons: list[EntityRef] = Field(default_factory=list)
    colleague_persons: list[EntityRef] = Field(default_factory=list)
    affiliated_enterprises: list[EntityRef] = Field(default_factory=list)
    participated_events: list[EntityRef] = Field(default_factory=list)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PersonExtractionResult(ProfileBase):
    """LLM Function Calling 专用：人员属性抽取结果。"""

    name_cn: str
    name_en: str | None = None
    gender: Gender
    nationality: str
    summary: str
    current_position: list[str]
    professional_domains: list[str]
    current_org: str | None = None
    highest_degree: Degree | None = None
    person_category: PersonCategory | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
