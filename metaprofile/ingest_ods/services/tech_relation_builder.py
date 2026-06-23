"""建 tech-tech 边。

P1: TECH_CONTAINS(L1 技术域 contains L2 具体技术)。

L1 IPC subclass 域 → L2 具体技术概念的树形归属边,为 Spec2/3 真 tech-tech
关系挖掘(演进/前置)铺路。仅当 L2 的 parent_ipc 已建为 L1 subclass 时建边。
"""
from __future__ import annotations

from datetime import datetime, timezone

from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple, RelationType


def build_containment_triples(
    *,
    l2_concepts: list[dict],
    l1_subclasses: set[str],
) -> list[RelationTriple]:
    """L2 概念归属某已建 L1 subclass → TECH_CONTAINS 边(ipc:X → concept:Y)。

    l2_concepts: [{"entity_id", "name", "parent_ipc"}]
    l1_subclasses: 已建 L1 的 subclass code 集合({"G06T", ...})
    """
    now = datetime.now(timezone.utc)
    out: list[RelationTriple] = []
    for c in l2_concepts:
        sub = c.get("parent_ipc")
        if not sub or sub not in l1_subclasses:
            continue
        out.append(
            RelationTriple(
                subject_id=f"ipc:{sub}",
                subject_type=EntityType.TECH,
                subject_name=sub,
                relation=RelationType.TECH_CONTAINS,
                object_id=c["entity_id"],
                object_type=EntityType.TECH,
                object_name=c["name"],
                evidence=None,
                confidence=1.0,
                source_doc_id=None,
                method=SourceMethod.RULE,
                extracted_at=now,
            )
        )
    return out
