"""单元测试:EntityType 卫星实体扩展(Task A1)。

为 ODS→画像管线全 48 关系进图做铺垫:5 类卫星实体
(STRATEGY/EVENT/ENTERPRISE/CONTRACT/PACKAGE)可作 RelationTriple 端点。
"""
from __future__ import annotations

from datetime import datetime, timezone

from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.schemas.relations import RelationTriple, RelationType


def test_satellite_entity_types_exist():
    """5 个卫星实体类型存在且取值正确。"""
    assert EntityType.STRATEGY.value == "战略规划"
    assert EntityType.EVENT.value == "事件"
    assert EntityType.ENTERPRISE.value == "企业"
    assert EntityType.CONTRACT.value == "采购合同"
    assert EntityType.PACKAGE.value == "项目包"


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
