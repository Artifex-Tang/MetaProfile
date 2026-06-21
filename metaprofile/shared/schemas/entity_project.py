"""
项目实体画像数据模型。字段严格遵循《实体画像数据规范》项目节。
"""
from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from metaprofile.shared.schemas.base import EntityRef, ProfileBase


class ProjectStatus(StrEnum):
    ONGOING = "进行中"
    FINISHED = "结束"
    TRANSFORMED = "成果已转化"


class BudgetActivity(StrEnum):
    BA1_BASIC = "基础技术研究BA-1"
    BA2_APPLIED = "应用技术研究BA-2"
    BA3_DEV = "先期技术开发BA-3"
    BA4_PROTOTYPE = "先期部件研制与样机开发BA-4"
    BA5_SYSTEM = "系统开发与演示验证BA-5"
    BA8_SOFTWARE = "软件研究/开发/测试和评估试点BA-8"


class ProjectHistory(ProfileBase):
    """项目发展历程。"""

    change_date: date | None = None
    change_description: str | None = None


class ProjectBudget(ProfileBase):
    """项目预算。"""

    budget_date: date | None = None
    amount: float = Field(..., description="预算金额（必填）")


class ProjectOutput(ProfileBase):
    """项目主要成果。"""

    name_history: str | None = Field(default=None, description="成果发布历程")
    formed_at: date | None = None
    tech_domains: list[str] = Field(default_factory=list)
    owner_orgs: list[str] = Field(default_factory=list)
    related_projects: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)


class ProjectProfile(ProfileBase):
    """项目画像。"""

    # ── 基本属性 ──
    project_id: str | None = None
    name_cn: list[str] = Field(default_factory=list, description="项目中文名称")
    name_en: list[str] = Field(default_factory=list, description="项目外文名称")
    name_other: list[str] = Field(default_factory=list)
    tech_domain: list[str] = Field(default_factory=list)
    sub_tech_domain: list[str] = Field(default_factory=list)
    start_date: date = Field(..., description="启动时间（必填）")
    cancel_date: date | None = None
    finish_date: date | None = None
    status: list[ProjectStatus] = Field(default_factory=list)
    budget_activities: list[BudgetActivity] = Field(default_factory=list)
    project_no: int = Field(..., description="项目编号（唯一，必填）")
    main_orgs: list[str] = Field(default_factory=list, description="主管机构（真数据可能缺）")
    undertaking_orgs: list[str] = Field(default_factory=list)
    undertaking_enterprises: list[str] = Field(default_factory=list)
    managers: list[str] = Field(default_factory=list)
    researchers: list[str] = Field(default_factory=list)
    background: list[str] = Field(default_factory=list)
    research_goal: str | None = None
    research_content: list[str] = Field(
        default_factory=list, description="主要研究内容（真数据可能缺）"
    )
    keywords: list[str] = Field(default_factory=list)
    progress: list[str] = Field(default_factory=list, description="主要进展（真数据可能缺）")
    application_prospect: str | None = None
    key_dates: list[date] = Field(default_factory=list)
    total_budget_million_usd: float | None = None
    invested_million_usd: float | None = None
    parent_package_name: str | None = None
    previous_phase_name: str | None = None

    # ── 扩展属性 ──
    histories: list[ProjectHistory] = Field(default_factory=list)
    budgets: list[ProjectBudget] = Field(default_factory=list)
    outputs: list[ProjectOutput] = Field(default_factory=list)

    # ── 关系 ──
    main_org_refs: list[EntityRef] = Field(default_factory=list)
    undertaking_org_refs: list[EntityRef] = Field(default_factory=list)
    strategy_refs: list[EntityRef] = Field(default_factory=list)
    next_phase_projects: list[EntityRef] = Field(default_factory=list)
    parent_package_refs: list[EntityRef] = Field(default_factory=list)
    sibling_package_refs: list[EntityRef] = Field(default_factory=list)
    manager_refs: list[EntityRef] = Field(default_factory=list)
    researcher_refs: list[EntityRef] = Field(default_factory=list)
    event_refs: list[EntityRef] = Field(default_factory=list)
    tech_refs: list[EntityRef] = Field(default_factory=list)
    enterprise_refs: list[EntityRef] = Field(default_factory=list)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ProjectExtractionResult(ProfileBase):
    """LLM Function Calling 专用：项目属性抽取结果。"""

    name_cn: list[str]
    name_en: list[str] = Field(default_factory=list)
    tech_domain: list[str]
    start_date: date
    project_no: int
    main_orgs: list[str]
    undertaking_orgs: list[str] = Field(default_factory=list)
    research_content: list[str]
    progress: list[str]
    research_goal: str | None = None
    total_budget_million_usd: float | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
