from unittest.mock import AsyncMock, patch

import pytest

from metaprofile.shared.db.neo4j import Neo4jRepo


def _sess_mock(rows):
    """mock get_neo4j_session：result.data() 返 rows。"""
    sess = AsyncMock()
    result = AsyncMock()
    result.data = AsyncMock(return_value=rows)
    sess.run = AsyncMock(return_value=result)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=sess)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_find_path_returns_nodes_and_rel_types():
    rows = [{
        "nodes": [{"entity_id": "A", "entity_type": "TECH", "name": "甲"},
                  {"entity_id": "B", "entity_type": "TECH", "tech_name_cn": "乙"}],
        "rels": ["演进", "资助"],
    }]
    repo = Neo4jRepo()
    with patch("metaprofile.shared.db.neo4j.get_neo4j_session", return_value=_sess_mock(rows)):
        paths = await repo.find_path(from_id="A", to_id="B", max_depth=3)
    assert len(paths) == 1
    p = paths[0]
    assert p["nodes"][0]["entity_id"] == "A"
    assert p["rel_types"] == ["演进", "资助"]


@pytest.mark.asyncio
async def test_find_related_chain_both_direction():
    rows = [{
        "nodes": [{"entity_id": "A", "entity_type": "TECH", "name": "甲"},
                  {"entity_id": "B", "entity_type": "TECH", "name": "乙"}],
        "rels": [{"type": "演进", "start": "A", "end": "B"}],
    }]
    repo = Neo4jRepo()
    with patch("metaprofile.shared.db.neo4j.get_neo4j_session", return_value=_sess_mock(rows)):
        res = await repo.find_related_chain(
            entity_id="A", label="Tech", rel_type="演进", depth=3, direction="both")
    assert len(res["nodes"]) == 2
    assert res["edges"][0]["rel_type"] == "演进"
    assert res["edges"][0]["source"] == "A"
    assert res["edges"][0]["target"] == "B"


@pytest.mark.asyncio
async def test_find_related_chain_empty():
    repo = Neo4jRepo()
    with patch("metaprofile.shared.db.neo4j.get_neo4j_session", return_value=_sess_mock([])):
        res = await repo.find_related_chain(
            entity_id="X", label="Tech", rel_type="演进", depth=2, direction="both")
    assert res == {"nodes": [], "edges": []}
