"""
关系类型定义（Neo4j 关系类型）。

完整覆盖《实体画像数据规范》关系节，**禁止**新增关系类型。
所有关系抽取（规则/LLM）必须从此枚举中选择。

例外：TECH_EVOLVE / TECH_PREREQ 经 2026-06-18 评审新增（技术-技术演进/前置），
为 Spec 2/3 真挖掘铺路；除此之外不得新增。
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from metaprofile.shared.schemas.base import EntityType, ProfileBase, SourceMethod


class RelationType(StrEnum):
    # 机构-机构
    ORG_PARENT = "隶属"
    ORG_CHILD = "下辖"
    ORG_SIBLING = "兄弟单位"
    ORG_COOPERATE = "合作"
    ORG_HISTORY = "沿革"
    ORG_FUND = "拨款或资助"
    ORG_EVALUATE = "评价"

    # 机构-战略规划
    ORG_PROPOSE_STRATEGY = "提出或开发"

    # 机构-项目
    ORG_FUND_PROJECT = "资助"
    ORG_UNDERTAKE_PROJECT = "承研"

    # 机构-人员
    ORG_EVALUATE_PERSON = "评价"
    ORG_EMPLOY = "雇佣"

    # 机构-事件
    ORG_PARTICIPATE_EVENT = "参与"

    # 机构-技术
    ORG_INVOLVE_TECH = "涉及"

    # 机构-企业
    ORG_COOP_ENTERPRISE = "合作"
    ORG_FUND_ENTERPRISE = "资助"

    # 机构-采购合同
    ORG_PUBLISH_CONTRACT = "发布"
    ORG_UNDERTAKE_CONTRACT = "承研"

    # 项目-机构
    PROJECT_MAIN_ORG = "主管"
    PROJECT_UNDERTAKE_ORG = "承研"

    # 项目-战略规划
    PROJECT_GUIDED_BY = "被指导"

    # 项目-项目
    PROJECT_NEXT_PHASE = "转阶段"
    PROJECT_BELONG_PACKAGE = "所属项目包"
    PROJECT_SIBLING_PACKAGE = "同属项目包"

    # 项目-人员
    PROJECT_MANAGER = "管理者"
    PROJECT_RESEARCHER = "研究者"

    # 项目-事件
    PROJECT_PARTICIPATE = "参与"

    # 项目-技术
    PROJECT_INVOLVE_TECH = "涉及"

    # 项目-企业
    PROJECT_UNDERTAKEN_BY_ENT = "被承研"

    # 人员-机构
    PERSON_AFFILIATED_ORG = "隶属"
    PERSON_EVALUATE_ORG = "评价"
    PERSON_EVALUATED_BY_ORG = "被评价"

    # 人员-战略规划
    PERSON_DRAFT_STRATEGY = "编写"

    # 人员-项目
    PERSON_MANAGE_PROJECT = "管理"
    PERSON_RESEARCH_PROJECT = "研究"

    # 人员-人员
    PERSON_COOPERATE = "合作"
    PERSON_EVALUATE_PERSON = "评价"
    PERSON_EVALUATED_BY_PERSON = "被评价"
    PERSON_SUPERIOR = "上级"
    PERSON_SUBORDINATE = "下级"
    PERSON_COLLEAGUE = "同事"

    # 人员-事件
    PERSON_PARTICIPATE_EVENT = "参与"

    # 人员-企业
    PERSON_AFFILIATED_ENT = "隶属"
    PERSON_EVALUATE_ENT = "评价"
    PERSON_EVALUATED_BY_ENT = "被评价"

    # 技术-机构 / 技术-人员 / 技术-企业
    TECH_CONTRIBUTOR = "贡献者"
    TECH_REVIEWED_BY = "被评议"

    # 技术-技术（2026-06-18 评审新增；演进/前置，为 Spec2/3 真挖掘铺路）
    TECH_EVOLVE = "演进"
    TECH_PREREQ = "前置"


class RelationTriple(ProfileBase):
    """关系三元组（关系抽取的输出格式）。"""

    subject_id: str
    subject_type: EntityType
    subject_name: str | None = None

    relation: RelationType

    object_id: str
    object_type: EntityType
    object_name: str | None = None

    evidence: str | None = Field(default=None, description="原文支撑片段")
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_doc_id: str | None = None
    method: SourceMethod = SourceMethod.RULE
    extracted_at: datetime
