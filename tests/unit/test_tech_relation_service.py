from unittest.mock import AsyncMock, patch

import pytest

from metaprofile.profile_tech.services.tech_relation_service import TechRelationService


@pytest.mark.asyncio
async def test_find_path_maps_names_types_and_real_relation():
    svc = TechRelationService()
    fake_paths = [{
        "nodes": [
            {"entity_id": "A", "entity_type": "TECH", "name": "甲"},
            {"entity_id": "O1", "entity_type": "ORG", "name": "某机构"},
            {"entity_id": "B", "entity_type": "TECH", "tech_name_cn": "乙"},
        ],
        "rel_types": ["涉及", "资助"],
    }]
    with patch.object(svc._neo4j, "find_path", AsyncMock(return_value=fake_paths)):
        res = await svc.find_path(from_id="A", to_id="B", max_depth=3)
    assert res.found is True
    assert len(res.paths) == 1
    s0, s1 = res.paths[0]
    assert s0.from_id == "A" and s0.from_name == "甲" and s0.from_type == "TECH"
    assert s0.to_id == "O1" and s0.to_name == "某机构" and s0.to_type == "ORG"
    assert s0.relation == "涉及"  # 真实关系，非 RELATED
    assert s1.relation == "资助"


@pytest.mark.asyncio
async def test_find_path_not_found():
    svc = TechRelationService()
    with patch.object(svc._neo4j, "find_path", AsyncMock(return_value=[])):
        res = await svc.find_path(from_id="A", to_id="Z", max_depth=3)
    assert res.found is False
    assert res.paths == []
