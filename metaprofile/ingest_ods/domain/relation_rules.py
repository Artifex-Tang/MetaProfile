"""表字段 → 关系三元组 规则（结构化隐含关系物化为图边）。

GAP1: 当前 structured 表只产 entity attrs（如 company.legal_person_name →
org.legal_person attr），而非 ORG-EMPLOY-PERSON 边。本模块用声明式规则把
表里的隐含关系物化为 RelationTriple，再由 orchestrator 在写图前用
NameIndex 解析端点为 PK(对齐 profile 节点)或保留 name: 卫星。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from metaprofile.ingest_ods.domain.mappings import _feat, _resolve
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple, RelationType


@dataclass
class StructRelationRule:
    """一条表→关系规则。

    current_as="subject": 抽取中的实体是关系主体(如 org 雇佣 person)。
    current_as="object":  抽取中的实体是关系客体(如 tech 被 org 涉及 → org INVOLVE tech)。
    obj_name_src: 取客体(或主体)名称的源(列名字符串 或 _feat(name) callable),同 mappings。
    is_list: 该字段是 list(如 Inventor/authors) → 每个元素一条关系。
    """

    obj_type: EntityType
    relation: RelationType
    obj_name_src: Any            # 列名(str) 或 _feat(name)
    current_as: str = "subject"  # "subject" | "object"
    is_list: bool = False


# 按 source_table 注册规则。subject_type 由表的 profile_type 决定(apply_mapping)。
RULES: dict[str, list[StructRelationRule]] = {
    "ods_company_basic_info": [   # profile_type=org
        # org --雇佣--> person(legal_person_name)
        StructRelationRule(EntityType.PERSON, RelationType.ORG_EMPLOY, "legal_person_name"),
    ],
    "ods_talent_info_cn": [        # profile_type=person
        # person --隶属--> org(employer)
        StructRelationRule(EntityType.ORG, RelationType.PERSON_AFFILIATED_ORG, "employer"),
    ],
    "ods_invention_patent_cn": [   # profile_type=tech
        # org(applicant) --涉及--> tech(current). current=object.
        StructRelationRule(
            EntityType.ORG, RelationType.ORG_INVOLVE_TECH, "applicant", current_as="object",
        ),
        # person(inventor) --贡献者--> tech(current). current=object. Inventor 从 features 取, list.
        StructRelationRule(
            EntityType.PERSON, RelationType.TECH_CONTRIBUTOR, _feat("Inventor"),
            current_as="object", is_list=True,
        ),
    ],
    "ods_science_literature": [    # profile_type=tech
        # person(authors) --贡献者--> tech(current). authors 可能 list 或逗号串.
        StructRelationRule(
            EntityType.PERSON, RelationType.TECH_CONTRIBUTOR, "authors",
            current_as="object", is_list=True,
        ),
    ],
    "ods_market_analysis_cn": [    # profile_type=project
        # purchaser 是项目的采购方(主管机构): project --主管--> org(purchaser). current=subject.
        StructRelationRule(
            EntityType.ORG, RelationType.PROJECT_MAIN_ORG, "purchaser", current_as="subject",
        ),
    ],
}


def _normalize(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_name_list(raw: Any, *, is_list: bool) -> list[str]:
    """规整字段值为 list[str]。is_list=True 时按 list/逗号串拆分;否则单值包成单元素 list。"""
    if is_list:
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, str):
            # authors 既可能 "A,B;C" 也可能纯单值
            items = raw.replace(";", ",").split(",")
        else:
            items = [raw]
        return [n for n in (_normalize(x) for x in items) if n]
    nm = _normalize(raw)
    return [nm] if nm else []


def extract_structured_relations(
    table: str,
    row: dict,
    current_entity_id: str,
    current_entity_type: EntityType,
) -> list[RelationTriple]:
    """从一行抽结构化关系。

    current_entity_id=当前实体的 PK(写图时对齐 profile 节点)。
    返回的 RelationTriple 端点 id 暂用 f"name:{name}" 占位 —— 由 orchestrator 的
    NameIndex 在写图前解析为 PK(命中)或保留 name:(卫星)。method=RULE。
    """
    rules = RULES.get(table)
    if not rules:
        return []
    out: list[RelationTriple] = []
    now = datetime.now(timezone.utc)
    for rule in rules:
        raw = _resolve(row, rule.obj_name_src)
        names = _to_name_list(raw, is_list=rule.is_list)
        for nm in names:
            other_id = f"name:{nm}"
            if rule.current_as == "subject":
                # current=subject, other=object
                tri = RelationTriple(
                    subject_id=current_entity_id,
                    subject_type=current_entity_type,
                    subject_name=None,
                    relation=rule.relation,
                    object_id=other_id,
                    object_type=rule.obj_type,
                    object_name=nm,
                    confidence=1.0,
                    source_doc_id=None,
                    method=SourceMethod.RULE,
                    extracted_at=now,
                )
            else:  # current=object
                tri = RelationTriple(
                    subject_id=other_id,
                    subject_type=rule.obj_type,
                    subject_name=nm,
                    relation=rule.relation,
                    object_id=current_entity_id,
                    object_type=current_entity_type,
                    object_name=None,
                    confidence=1.0,
                    source_doc_id=None,
                    method=SourceMethod.RULE,
                    extracted_at=now,
                )
            out.append(tri)
    return out
