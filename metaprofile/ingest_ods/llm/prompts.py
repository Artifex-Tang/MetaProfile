"""LLM 结构化输出 schema + 关系谓词→RelationType 映射 + prompt 文本。"""
from __future__ import annotations

from datetime import date

from pydantic import Field

from metaprofile.shared.schemas.base import ProfileBase
from metaprofile.shared.schemas.relations import RelationType


class MinedEntity(ProfileBase):
    type: str                         # tech/org/person/project
    name: str
    attrs: dict = Field(default_factory=dict)
    veracity_hint: float = Field(default=0.0, ge=0.0, le=1.0)
    as_of: date | None = None


class MinedRelation(ProfileBase):
    subject_name: str
    subject_type: str
    object_name: str
    object_type: str
    predicate: str                    # 中文谓词，map_predicate 归一
    evidence: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ScoreOutput(ProfileBase):
    veracity: float = Field(..., ge=0.0, le=1.0)
    timeliness: float = Field(..., ge=0.0, le=1.0)
    reason: str | None = None


class DisambigResult(ProfileBase):
    same: bool
    reason: str | None = None


# 谓词 → RelationType（按 主/客体类型 上下文消歧同形谓词）
# 主体/客体类型键使用 LLM 期望的小写词表(匹配 content_miner 直接透传的 LLM type 串):
#   机构=org 人员=person 项目=project 技术=tech
#   卫星实体: 战略规划=strategy 事件=event 企业=enterprise
#             采购合同=contract 项目包=package
# 同值谓词(隶属/合作/评价/资助/承研/涉及/参与 等)按 (主,客) 元组消歧。
_PREDICATE_MAP: dict[tuple[str, str, str], RelationType] = {
    # —— 机构-机构 ——
    ("隶属", "org", "org"): RelationType.ORG_PARENT,
    ("下辖", "org", "org"): RelationType.ORG_CHILD,
    ("兄弟单位", "org", "org"): RelationType.ORG_SIBLING,
    ("合作", "org", "org"): RelationType.ORG_COOPERATE,
    ("沿革", "org", "org"): RelationType.ORG_HISTORY,
    ("拨款或资助", "org", "org"): RelationType.ORG_FUND,
    ("评价", "org", "org"): RelationType.ORG_EVALUATE,

    # —— 机构-战略规划 ——
    ("提出或开发", "org", "strategy"): RelationType.ORG_PROPOSE_STRATEGY,

    # —— 机构-项目 ——
    ("资助", "org", "project"): RelationType.ORG_FUND_PROJECT,
    ("承研", "org", "project"): RelationType.ORG_UNDERTAKE_PROJECT,

    # —— 机构-人员 ——
    ("评价", "org", "person"): RelationType.ORG_EVALUATE_PERSON,
    ("雇佣", "org", "person"): RelationType.ORG_EMPLOY,

    # —— 机构-事件 ——
    ("参与", "org", "event"): RelationType.ORG_PARTICIPATE_EVENT,

    # —— 机构-技术 ——
    ("涉及", "org", "tech"): RelationType.ORG_INVOLVE_TECH,

    # —— 机构-企业 ——
    ("合作", "org", "enterprise"): RelationType.ORG_COOP_ENTERPRISE,
    ("资助", "org", "enterprise"): RelationType.ORG_FUND_ENTERPRISE,

    # —— 机构-采购合同 ——
    ("发布", "org", "contract"): RelationType.ORG_PUBLISH_CONTRACT,
    ("承研", "org", "contract"): RelationType.ORG_UNDERTAKE_CONTRACT,

    # —— 项目-机构 ——
    ("主管", "project", "org"): RelationType.PROJECT_MAIN_ORG,
    ("承研", "project", "org"): RelationType.PROJECT_UNDERTAKE_ORG,

    # —— 项目-战略规划 ——
    ("被指导", "project", "strategy"): RelationType.PROJECT_GUIDED_BY,

    # —— 项目-项目 ——
    ("转阶段", "project", "project"): RelationType.PROJECT_NEXT_PHASE,
    ("所属项目包", "project", "project"): RelationType.PROJECT_BELONG_PACKAGE,
    ("同属项目包", "project", "project"): RelationType.PROJECT_SIBLING_PACKAGE,

    # —— 项目-人员 ——
    ("管理者", "project", "person"): RelationType.PROJECT_MANAGER,
    ("研究者", "project", "person"): RelationType.PROJECT_RESEARCHER,

    # —— 项目-事件 ——
    ("参与", "project", "event"): RelationType.PROJECT_PARTICIPATE,

    # —— 项目-技术 ——
    ("涉及", "project", "tech"): RelationType.PROJECT_INVOLVE_TECH,

    # —— 项目-企业 ——
    ("被承研", "project", "enterprise"): RelationType.PROJECT_UNDERTAKEN_BY_ENT,

    # —— 人员-机构 ——
    ("隶属", "person", "org"): RelationType.PERSON_AFFILIATED_ORG,
    ("评价", "person", "org"): RelationType.PERSON_EVALUATE_ORG,
    ("被评价", "person", "org"): RelationType.PERSON_EVALUATED_BY_ORG,

    # —— 人员-战略规划 ——
    ("编写", "person", "strategy"): RelationType.PERSON_DRAFT_STRATEGY,

    # —— 人员-项目 ——
    ("管理", "person", "project"): RelationType.PERSON_MANAGE_PROJECT,
    ("研究", "person", "project"): RelationType.PERSON_RESEARCH_PROJECT,

    # —— 人员-人员 ——
    ("合作", "person", "person"): RelationType.PERSON_COOPERATE,
    ("评价", "person", "person"): RelationType.PERSON_EVALUATE_PERSON,
    ("被评价", "person", "person"): RelationType.PERSON_EVALUATED_BY_PERSON,
    ("上级", "person", "person"): RelationType.PERSON_SUPERIOR,
    ("下级", "person", "person"): RelationType.PERSON_SUBORDINATE,
    ("同事", "person", "person"): RelationType.PERSON_COLLEAGUE,

    # —— 人员-事件 ——
    ("参与", "person", "event"): RelationType.PERSON_PARTICIPATE_EVENT,

    # —— 人员-企业 ——
    ("隶属", "person", "enterprise"): RelationType.PERSON_AFFILIATED_ENT,
    ("评价", "person", "enterprise"): RelationType.PERSON_EVALUATE_ENT,
    ("被评价", "person", "enterprise"): RelationType.PERSON_EVALUATED_BY_ENT,

    # —— 技术-机构 / 技术-人员 / 技术-企业 ——
    ("贡献者", "person", "tech"): RelationType.TECH_CONTRIBUTOR,
    ("被评议", "tech", "enterprise"): RelationType.TECH_REVIEWED_BY,

    # —— 技术-技术(2026-06-18 评审新增;Spec2/3 真挖掘铺路) ——
    ("演进", "tech", "tech"): RelationType.TECH_EVOLVE,
    ("前置", "tech", "tech"): RelationType.TECH_PREREQ,

    # —— 别名(LLM 同义词容错;不新增覆盖,只增强召回) ——
    ("研发", "org", "tech"): RelationType.ORG_INVOLVE_TECH,        # 同 涉及
    ("中标", "org", "project"): RelationType.ORG_UNDERTAKE_PROJECT,  # 同 承研
    ("提出或开发", "org", "tech"): RelationType.ORG_INVOLVE_TECH,   # 见 ORG_PROPOSE_STRATEGY
}


def map_predicate(predicate: str, subject_type: str, object_type: str) -> RelationType | None:
    return _PREDICATE_MAP.get((predicate, subject_type, object_type))


MINE_SYSTEM_PROMPT = """你是产业情报抽取专家。从给定正文抽取实体（技术/项目/机构/人员）与它们之间的关系。
仅输出 JSON：{"entities":[...],"relations":[...]}。
实体：{type,name,attrs,veracity_hint(0-1 被文支撑程度),as_of(YYYY-MM-DD 或 null)}。
关系：{subject_name,subject_type,object_name,object_type,predicate(中文:隶属/涉及/中标/承研/资助/管理/研究/合作/贡献者 等),evidence(原文片段),confidence(0-1)}。
无依据不编造。"""

SCORE_SYSTEM_PROMPT = """你是数据质量评估专家。基于给定实体的属性与来源信息，评判：
veracity(真实性 0-1：主张被源支撑/无矛盾/源可信度)、timeliness(时效性 0-1：信息是否仍当前)。
输出 JSON：{"veracity":float,"timeliness":float,"reason":str}。"""

DISAMBIG_SYSTEM_PROMPT = """你是实体消歧专家。判断两个实体描述是否指同一对象。
输出 JSON：{"same":bool,"reason":str}。不确定时 same=false。"""
