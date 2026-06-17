"""单元测试:EntityType 卫星实体扩展(Task A1)。

为 ODS→画像管线全 48 关系进图做铺垫:5 类卫星实体
(STRATEGY/EVENT/ENTERPRISE/CONTRACT/PACKAGE)可作 RelationTriple 端点。
"""
from __future__ import annotations

from datetime import datetime, timezone

from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.schemas.relations import RelationTriple, RelationType


def test_satellite_entity_types_exist():
    """5 个卫星实体类型存在,值用 ASCII(同 TECH/ORG/...,因 .value 是 load-bearing 标识符)。"""
    assert EntityType.STRATEGY.value == "STRATEGY"
    assert EntityType.EVENT.value == "EVENT"
    assert EntityType.ENTERPRISE.value == "ENTERPRISE"
    assert EntityType.CONTRACT.value == "CONTRACT"
    assert EntityType.PACKAGE.value == "PACKAGE"


def test_relation_triple_accepts_satellite_endpoints():
    """卫星实体类型可作关系端点(全 48 关系进图前提)。"""
    tri = RelationTriple(
        subject_id="ORG_1",
        subject_type=EntityType.ORG,
        subject_name="甲公司",
        relation=RelationType.ORG_PROPOSE_STRATEGY,
        object_id="name:某战略",
        object_type=EntityType.STRATEGY,
        object_name="某战略",
        confidence=0.9,
        extracted_at=datetime.now(timezone.utc),
    )
    assert tri.object_type == EntityType.STRATEGY
    assert tri.subject_type == EntityType.ORG


def test_neo4j_labels_cover_satellites():
    """Neo4j label 图覆盖 5 卫星类(两个消费点:repo EntityType 键 + triple_writer value 键)。"""
    from metaprofile.foundation.storage.neo4j_repo import _ENTITY_LABELS as repo_labels
    from metaprofile.foundation.relation.triple_writer import _ENTITY_LABELS as tw_labels

    satellites = (EntityType.STRATEGY, EntityType.EVENT, EntityType.ENTERPRISE,
                  EntityType.CONTRACT, EntityType.PACKAGE)
    for et in satellites:
        assert repo_labels[et], f"neo4j_repo 缺 label: {et}"
        assert tw_labels[et.value], f"triple_writer 缺 label: {et.value}"
    # label 值合理(首字母大写英文)
    assert repo_labels[EntityType.STRATEGY] == "Strategy"
    assert tw_labels["ENTERPRISE"] == "Enterprise"
