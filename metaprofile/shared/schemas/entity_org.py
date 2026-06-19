"""
机构实体画像数据模型。字段严格遵循《实体画像数据规范》机构节。
"""
from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from metaprofile.shared.schemas.base import EntityRef, ProfileBase, ReviewType


class OrgType(StrEnum):
    GOVT = "管理机构"
    RESEARCH = "科研机构"
    UNIVERSITY = "高校"
    ENTERPRISE = "企业"
    CONSULT = "咨询机构"
    TESTING = "试验鉴定机构"
    OTHER = "其他"


class OrgNature(StrEnum):
    ABSTRACT = "抽象机构"
    ENTITY = "实体机构"


class OrgHistory(ProfileBase):
    """机构发展沿革。"""

    change_date: date = Field(..., description="机构变动时间（必填）")
    change_description: str = Field(..., description="机构变动情况描述（必填）")


class OrgAffiliation(ProfileBase):
    """隶属单位变化。"""

    change_date: date | None = None
    parent_name: str = Field(..., description="隶属单位名称（必填）")


class OrgAward(ProfileBase):
    """荣誉奖励。"""

    description: str | None = None
    name: str | None = None
    reason: str | None = None
    award_date: date | None = None
    level: str | None = None
    award_type: str | None = Field(default=None, description="科技奖励/人员奖励")


class OrgBudget(ProfileBase):
    """机构预算情况。"""

    funder_name: str | None = None
    budget_date: date | None = None
    amount_usd: float | None = Field(default=None, description="预算金额（美元）")


class OrgFundingReceived(ProfileBase):
    """接受资助情况。"""

    funder_name: str | None = None
    fund_date: date | None = None
    amount_or_equipment: str | None = None


class OrgOutput(ProfileBase):
    """主要成果。"""

    name: str | None = None
    form: str | None = Field(
        default=None, description="论文/专著/专利/报告/技术标准规范/其他"
    )
    author: str | None = None
    publish_date: date | None = None
    attachment: str | None = None


class OrgReview(ProfileBase):
    """社会评议及影响。"""

    content: str | None = None
    review_org: str | None = None
    review_person: str | None = None
    review_type: ReviewType | None = None
    review_date: date | None = None


class OrgAddress(ProfileBase):
    """机构地址。"""

    address: str = Field(..., description="地址名称（必填）")
    longitude: float | None = None
    latitude: float | None = None


class OrgActivity(ProfileBase):
    """重大科研活动。"""

    activity_type: str | None = Field(
        default=None, description="成果展示会/研讨会/重大科研试验"
    )
    content: str | None = None
    activity_date: date | None = None
    locations: list[str] = Field(default_factory=list)


class OrgTeam(ProfileBase):
    """科技队伍。"""

    top_talents: list[str] = Field(default_factory=list)
    award_winners: list[str] = Field(default_factory=list)
    team_size: int | None = None
    talent_type: str | None = None


class OrgFacility(ProfileBase):
    """科研设施。"""

    name: str | None = None
    purpose: str | None = None
    experiment_status: str | None = None
    launch_date: date | None = None
    construction_cost_wan_usd: float | None = None


class OrgProfile(ProfileBase):
    """机构画像。"""

    # ── 基本属性 ──
    org_id: str | None = None
    name_cn: str = Field(default="", description="机构中文名称")
    name_en: str = Field(default="", description="机构外文名称")
    name_other: list[str] = Field(default_factory=list)
    country: str = Field(..., description="国家或地区（必填）")
    founded_date: date = Field(..., description="创建时间（必填）")
    dissolved_date: date | None = None
    operating_years: int = Field(..., description="运行时间（年，必填）")
    website: str | None = None
    summary: str = Field(..., description="机构简介（必填）")
    org_types: list[OrgType] = Field(..., min_length=1, description="机构类型")
    nature: OrgNature = Field(..., description="机构性质")
    function: str = Field(..., description="机构职能（必填）")
    scale: int | None = Field(default=None, description="机构规模（人）")
    tech_domains: list[str] = Field(default_factory=list)
    predecessor_names: list[str] = Field(default_factory=list)
    departments: str | None = None
    strategic_plans: list[str] = Field(default_factory=list)
    evaluation_report: str | None = None
    new_key_projects: list[str] = Field(default_factory=list)
    remark: str | None = None

    # ── 扩展属性 ──
    histories: list[OrgHistory] = Field(default_factory=list)
    affiliations: list[OrgAffiliation] = Field(default_factory=list)
    awards: list[OrgAward] = Field(default_factory=list)
    budgets: list[OrgBudget] = Field(default_factory=list)
    fundings_received: list[OrgFundingReceived] = Field(default_factory=list)
    outputs: list[OrgOutput] = Field(default_factory=list)
    reviews: list[OrgReview] = Field(default_factory=list)
    addresses: list[OrgAddress] = Field(default_factory=list)
    activities: list[OrgActivity] = Field(default_factory=list)
    team: OrgTeam | None = None
    facilities: list[OrgFacility] = Field(default_factory=list)

    # ── 关系 ──
    parent_orgs: list[EntityRef] = Field(default_factory=list)
    child_orgs: list[EntityRef] = Field(default_factory=list)
    sibling_orgs: list[EntityRef] = Field(default_factory=list)
    cooperated_orgs: list[EntityRef] = Field(default_factory=list)
    funded_projects: list[EntityRef] = Field(default_factory=list)
    undertaken_projects: list[EntityRef] = Field(default_factory=list)
    employees: list[EntityRef] = Field(default_factory=list)
    related_techs: list[EntityRef] = Field(default_factory=list)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class OrgExtractionResult(ProfileBase):
    """LLM Function Calling 专用：机构属性抽取结果。"""

    name_cn: str
    name_en: str | None = None
    country: str
    founded_date: date | None = None
    summary: str
    org_types: list[OrgType]
    nature: OrgNature
    function: str
    tech_domains: list[str]
    scale: int | None = None
    website: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
