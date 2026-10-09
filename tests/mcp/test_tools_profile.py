"""画像端点的工具：参数如何映射到后端 REST 路径与请求体。"""
from __future__ import annotations

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from tests.mcp.conftest import call_tool, mcp_for

# (端点 slug, 后端路径里的类型段)
PROFILE_ENDPOINTS = [
    ("tech-profile", "tech"),
    ("project-profile", "project"),
    ("org-profile", "org"),
    ("person-profile", "person"),
]


@pytest.fixture(params=PROFILE_ENDPOINTS, ids=[s for s, _ in PROFILE_ENDPOINTS])
def profile_ctx(request, fake_client):
    slug, ptype = request.param
    return mcp_for(slug, fake_client), ptype, fake_client


async def test_search_hits_type_specific_path(profile_ctx):
    mcp, ptype, client = profile_ctx

    await call_tool(mcp, "search_profiles", {"keyword": "量子"})

    assert client.last["method"] == "POST"
    assert client.last["path"] == f"/profile/{ptype}/search"


async def test_search_maps_domain_to_type_prefixed_field(profile_ctx):
    """SearchRequest 用 extra='forbid'，domain 必须映射成 {type}_domain 才不会 422。"""
    mcp, ptype, client = profile_ctx

    await call_tool(mcp, "search_profiles", {"domain": ["材料", "能源"]})

    body = client.last["json"]
    assert body[f"{ptype}_domain"] == ["材料", "能源"]
    assert "domain" not in body


async def test_search_omits_none_fields(profile_ctx):
    mcp, _, client = profile_ctx

    await call_tool(mcp, "search_profiles", {"keyword": "AI"})

    assert client.last["json"] == {"keyword": "AI", "page": 1, "page_size": 20}


async def test_search_passes_pagination_and_dates(profile_ctx):
    mcp, _, client = profile_ctx

    await call_tool(
        mcp,
        "search_profiles",
        {
            "invention_date_from": "2020-01-01",
            "invention_date_to": "2024-12-31",
            "page": 3,
            "page_size": 50,
        },
    )

    body = client.last["json"]
    assert body["invention_date_from"] == "2020-01-01"
    assert body["invention_date_to"] == "2024-12-31"
    assert body["page"] == 3
    assert body["page_size"] == 50


async def test_get_profile(profile_ctx):
    mcp, ptype, client = profile_ctx

    await call_tool(mcp, "get_profile", {"profile_id": "X1"})

    assert client.last == {
        "method": "GET",
        "path": f"/profile/{ptype}/X1",
        "params": None,
    }


async def test_batch_maps_ids_to_type_prefixed_field(profile_ctx):
    """BatchQueryRequest 字段名是 {type}_ids（tech_ids / org_ids ...）。"""
    mcp, ptype, client = profile_ctx

    await call_tool(mcp, "batch_get_profiles", {"profile_ids": ["a", "b"]})

    assert client.last["path"] == f"/profile/{ptype}/batch"
    assert client.last["json"] == {f"{ptype}_ids": ["a", "b"]}


async def test_stats(profile_ctx):
    mcp, ptype, client = profile_ctx

    await call_tool(mcp, "get_profile_stats", {})

    assert client.last["method"] == "GET"
    assert client.last["path"] == f"/stats/{ptype}"


async def test_changes_requires_since_and_omits_none_until(profile_ctx):
    mcp, ptype, client = profile_ctx

    await call_tool(mcp, "list_profile_changes", {"since": "2026-01-01T00:00:00"})

    assert client.last["path"] == f"/profile/{ptype}/changes"
    assert client.last["params"]["since"] == "2026-01-01T00:00:00"
    assert client.last["params"]["limit"] == 100
    assert "until" not in client.last["params"]


async def test_relations(profile_ctx):
    mcp, ptype, client = profile_ctx

    await call_tool(mcp, "get_relations", {"profile_id": "N9"})

    assert client.last["path"] == f"/relation/{ptype}/N9"
    assert client.last["params"]["limit"] == 100


async def test_relations_passes_relation_type_filter(profile_ctx):
    mcp, _, client = profile_ctx

    await call_tool(
        mcp, "get_relations", {"profile_id": "O1", "relation_type": "COOPERATE", "limit": 10}
    )

    assert client.last["params"] == {"relation_type": "COOPERATE", "limit": 10}


async def test_find_relation_path(profile_ctx):
    mcp, ptype, client = profile_ctx

    await call_tool(mcp, "find_relation_path", {"from_id": "A", "to_id": "B"})

    assert client.last["method"] == "POST"
    assert client.last["path"] == f"/relation/{ptype}/path"
    assert client.last["json"] == {"from_id": "A", "to_id": "B", "max_depth": 4}


# ── 技术端点专有 ──────────────────────────────────────────────


async def test_get_tech_relation_defaults(fake_client):
    mcp = mcp_for("tech-profile", fake_client)

    await call_tool(mcp, "get_tech_relation", {"tech_id": "T7"})

    assert fake_client.last["path"] == "/relation/tech/T7/tech-relation"
    assert fake_client.last["params"] == {"viewpoint": "evolve", "depth": 4}


async def test_get_tech_relation_prereq_viewpoint(fake_client):
    mcp = mcp_for("tech-profile", fake_client)

    await call_tool(mcp, "get_tech_relation", {"tech_id": "T7", "viewpoint": "prereq", "depth": 2})

    assert fake_client.last["params"] == {"viewpoint": "prereq", "depth": 2}


async def test_get_tech_relation_rejects_bad_viewpoint(fake_client):
    """后端 pattern 限定 evolve|prereq，工具层应先拦住而不是打到后端拿 422。"""
    mcp = mcp_for("tech-profile", fake_client)

    with pytest.raises(ToolError, match="literal_error"):
        await call_tool(mcp, "get_tech_relation", {"tech_id": "T7", "viewpoint": "sideways"})
