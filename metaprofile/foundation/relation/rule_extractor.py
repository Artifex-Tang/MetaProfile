"""
基于规则的关系抽取。

策略：
- 共现实体对 + 触发词窗口 → RelationType
- 每种关系类型维护一组触发词模式（正则）
- 命中最高优先级规则；未命中返回 None
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import NamedTuple

from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple, RelationType


class EntitySpan(NamedTuple):
    entity_id: str
    entity_type: EntityType
    entity_name: str
    start: int
    end: int


# 触发词规则表：(subject_type, object_type, relation, patterns)
# patterns 在 subject-to-object 的窗口文本内匹配
_RULES: list[tuple[EntityType, EntityType, RelationType, list[str]]] = [
    # ORG-ORG
    (EntityType.ORG, EntityType.ORG, RelationType.ORG_PARENT,
     [r"隶属于", r"归属于", r"属于.*下属", r"上级单位"]),
    (EntityType.ORG, EntityType.ORG, RelationType.ORG_COOPERATE,
     [r"与.*合作", r"联合.*开展", r"共同.*签署"]),
    (EntityType.ORG, EntityType.ORG, RelationType.ORG_FUND,
     [r"资助", r"拨款", r"给予.*经费"]),
    # ORG-PROJECT
    (EntityType.ORG, EntityType.PROJECT, RelationType.ORG_FUND_PROJECT,
     [r"资助", r"立项", r"拨款.*项目", r"支持.*项目"]),
    (EntityType.ORG, EntityType.PROJECT, RelationType.ORG_UNDERTAKE_PROJECT,
     [r"承担", r"承研", r"负责.*项目", r"执行.*项目"]),
    # ORG-PERSON
    (EntityType.ORG, EntityType.PERSON, RelationType.ORG_EMPLOY,
     [r"雇用", r"录用", r"任命", r"聘请", r"工作于"]),
    # PROJECT-PERSON
    (EntityType.PROJECT, EntityType.PERSON, RelationType.PROJECT_MANAGER,
     [r"负责人", r"项目负责人", r"主持人"]),
    (EntityType.PROJECT, EntityType.PERSON, RelationType.PROJECT_RESEARCHER,
     [r"参与", r"研究人员", r"课题组成员"]),
    # PROJECT-ORG
    (EntityType.PROJECT, EntityType.ORG, RelationType.PROJECT_MAIN_ORG,
     [r"主管单位", r"主管部门", r"归口管理"]),
    (EntityType.PROJECT, EntityType.ORG, RelationType.PROJECT_UNDERTAKE_ORG,
     [r"承担单位", r"承研单位", r"依托单位"]),
    # PROJECT-TECH
    (EntityType.PROJECT, EntityType.TECH, RelationType.PROJECT_INVOLVE_TECH,
     [r"研究.*技术", r"攻关.*技术", r"涉及.*技术", r"采用"]),
    # PERSON-ORG
    (EntityType.PERSON, EntityType.ORG, RelationType.PERSON_AFFILIATED_ORG,
     [r"就职于", r"任职于", r"供职于", r"工作在", r"研究员"]),
    # PERSON-PROJECT
    (EntityType.PERSON, EntityType.PROJECT, RelationType.PERSON_MANAGE_PROJECT,
     [r"主持", r"负责", r"担任.*负责人"]),
    (EntityType.PERSON, EntityType.PROJECT, RelationType.PERSON_RESEARCH_PROJECT,
     [r"参与", r"研究", r"承担.*研究"]),
    # PERSON-PERSON
    (EntityType.PERSON, EntityType.PERSON, RelationType.PERSON_COOPERATE,
     [r"与.*合作", r"联合.*发表", r"共同.*研究"]),
    # TECH-ORG
    (EntityType.TECH, EntityType.ORG, RelationType.TECH_CONTRIBUTOR,
     [r"由.*研发", r"由.*开发", r"由.*发明"]),
]

# 编译正则，并附上优先级（列表位置）
_COMPILED: list[tuple[EntityType, EntityType, RelationType, list[re.Pattern[str]]]] = [
    (subj_type, obj_type, rel, [re.compile(p) for p in patterns])
    for subj_type, obj_type, rel, patterns in _RULES
]

_WINDOW = 80  # 实体间上下文窗口（字符）


def extract_relations(
    text: str,
    spans: list[EntitySpan],
    *,
    source_doc_id: str | None = None,
    min_confidence: float = 0.6,
) -> list[RelationTriple]:
    """
    对 text 中共现的实体对，用规则检测是否存在关系。

    Args:
        text: 原始文本
        spans: 已识别的实体跨度列表（含 entity_id）
        source_doc_id: 来源文档 ID
        min_confidence: 规则置信度固定为 0.75，此参数用于过滤

    Returns:
        所有命中规则的关系三元组
    """
    results: list[RelationTriple] = []
    now = datetime.now(timezone.utc)

    for i, subj in enumerate(spans):
        for j, obj in enumerate(spans):
            if i == j:
                continue
            window = _get_window(text, subj, obj)
            rel = _match_rules(subj.entity_type, obj.entity_type, window)
            if rel is None:
                continue
            confidence = 0.75
            if confidence < min_confidence:
                continue
            evidence = _make_evidence(text, subj, obj)
            results.append(
                RelationTriple(
                    subject_id=subj.entity_id,
                    subject_type=subj.entity_type,
                    subject_name=subj.entity_name,
                    relation=rel,
                    object_id=obj.entity_id,
                    object_type=obj.entity_type,
                    object_name=obj.entity_name,
                    evidence=evidence,
                    confidence=confidence,
                    source_doc_id=source_doc_id,
                    method=SourceMethod.RULE,
                    extracted_at=now,
                )
            )

    return results


# ─── helpers ────────────────────────────────────────────────────────────────

def _get_window(text: str, subj: EntitySpan, obj: EntitySpan) -> str:
    """取两个实体之间（及周边 _WINDOW 字符）的文本片段。"""
    lo = min(subj.end, obj.end)
    hi = max(subj.start, obj.start)
    # entities may be in any order
    between_start = min(subj.end, obj.end)
    between_end = max(subj.start, obj.start)
    if between_start > between_end:
        # no gap: overlapping or adjacent, use surrounding window
        center = (subj.start + obj.end) // 2
        return text[max(0, center - _WINDOW): center + _WINDOW]
    gap = text[between_start:between_end]
    # extend window outward
    ext_start = max(0, between_start - _WINDOW // 2)
    ext_end = min(len(text), between_end + _WINDOW // 2)
    return text[ext_start:ext_end]


def _match_rules(
    subj_type: EntityType,
    obj_type: EntityType,
    window: str,
) -> RelationType | None:
    for rule_subj, rule_obj, rel, patterns in _COMPILED:
        if rule_subj != subj_type or rule_obj != obj_type:
            continue
        for pat in patterns:
            if pat.search(window):
                return rel
    return None


def _make_evidence(text: str, subj: EntitySpan, obj: EntitySpan) -> str:
    lo = min(subj.start, obj.start)
    hi = max(subj.end, obj.end)
    start = max(0, lo - 20)
    end = min(len(text), hi + 20)
    return text[start:end]
