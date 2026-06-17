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
_PREDICATE_MAP: dict[tuple[str, str, str], RelationType] = {
    ("隶属", "person", "org"): RelationType.PERSON_AFFILIATED_ORG,
    ("隶属", "org", "org"): RelationType.ORG_PARENT,
    ("雇佣", "org", "person"): RelationType.ORG_EMPLOY,
    ("涉及", "org", "tech"): RelationType.ORG_INVOLVE_TECH,
    ("涉及", "project", "tech"): RelationType.PROJECT_INVOLVE_TECH,
    ("贡献者", "person", "tech"): RelationType.TECH_CONTRIBUTOR,
    ("研发", "org", "tech"): RelationType.ORG_INVOLVE_TECH,
    ("承研", "org", "project"): RelationType.ORG_UNDERTAKE_PROJECT,
    ("中标", "org", "project"): RelationType.ORG_UNDERTAKE_PROJECT,
    ("资助", "org", "project"): RelationType.ORG_FUND_PROJECT,
    ("管理", "person", "project"): RelationType.PERSON_MANAGE_PROJECT,
    ("研究", "person", "project"): RelationType.PERSON_RESEARCH_PROJECT,
    ("合作", "org", "org"): RelationType.ORG_COOPERATE,
    ("合作", "person", "person"): RelationType.PERSON_COOPERATE,
    ("提出或开发", "org", "tech"): RelationType.ORG_INVOLVE_TECH,
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
