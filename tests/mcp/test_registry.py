"""7 个 MCP 端点的注册表约束。

这些是对外契约：slug 进 URL、key 进客户端配置，改一个字都会让已发出去的配置失效。
"""
from __future__ import annotations

import pytest

from metaprofile.mcp_server.registry import (
    SERVICE_BY_SLUG,
    SERVICES,
    TOTAL_TOOL_COUNT,
)

# 对外已发布的契约，不允许悄悄改
EXPECTED = {
    "tech-profile": ("techProfile", 8),
    "project-profile": ("projectProfile", 7),
    "org-profile": ("orgProfile", 7),
    "person-profile": ("personProfile", 7),
    "scan-monitor": ("scanMonitor", 3),
    "new-tech-discovery": ("newTechDiscovery", 3),
    "topic-selection": ("topicSelection", 2),
}

# 只读部署不可用的能力，泄漏进任何一个端点都算 bug
FORBIDDEN_SUBSTRINGS = (
    "enrich", "translate", "import", "update", "semantic",
    "scan_", "verify", "generate", "feedback", "delete",
)


def test_exactly_seven_services():
    assert len(SERVICES) == 7


def test_slugs_and_keys_match_published_contract():
    actual = {s.slug: (s.key, len(s.tool_names)) for s in SERVICES}

    assert actual == EXPECTED


def test_total_tool_count():
    assert TOTAL_TOOL_COUNT == 37


def test_slugs_are_url_safe_kebab_case():
    for s in SERVICES:
        assert s.slug == s.slug.lower()
        assert " " not in s.slug and "_" not in s.slug
        assert s.path == f"/mcp/{s.slug}"


def test_keys_are_unique():
    keys = [s.key for s in SERVICES]

    assert len(set(keys)) == len(keys)


def test_every_service_has_title_and_instructions():
    for s in SERVICES:
        assert s.title, f"{s.slug} 缺 title"
        assert len(s.instructions) >= 20, f"{s.slug} 的 instructions 太短"


@pytest.mark.parametrize("slug", list(EXPECTED))
@pytest.mark.parametrize("bad", FORBIDDEN_SUBSTRINGS)
def test_no_write_capability_in_any_service(slug, bad):
    names = SERVICE_BY_SLUG[slug].tool_names

    assert not [n for n in names if bad in n], f"{slug} 暴露了只读模式不可用的能力: {bad}"


@pytest.mark.parametrize("slug,expected", [(k, v[1]) for k, v in EXPECTED.items()])
async def test_registered_tool_count_matches_declaration(servers, slug, expected):
    """注册表声明的数量必须与实际注册进 FastMCP 的一致。"""
    tools = await servers[slug].list_tools()

    assert len(tools) == expected
    assert {t.name for t in tools} == set(SERVICE_BY_SLUG[slug].tool_names)


async def test_every_tool_has_description(servers):
    """描述是模型选工具的唯一依据。

    特别防回归：曾经用 f-string 写文档字符串，__doc__ 静默变 None，描述全丢。
    """
    for slug, mcp in servers.items():
        for tool in await mcp.list_tools():
            assert tool.description, f"{slug}/{tool.name} 缺 description"
            assert len(tool.description) >= 10, f"{slug}/{tool.name} 描述过短"


async def test_profile_tools_have_no_profile_type_param(servers):
    """类型已绑定在端点上，不该再出现在参数里（否则等于回到单服务形态）。"""
    for slug in ("tech-profile", "org-profile"):
        for tool in await servers[slug].list_tools():
            assert "profile_type" not in tool.inputSchema.get("properties", {})


async def test_tech_relation_only_on_tech_endpoint(servers):
    for slug, mcp in servers.items():
        names = {t.name for t in await mcp.list_tools()}
        if slug == "tech-profile":
            assert "get_tech_relation" in names
        else:
            assert "get_tech_relation" not in names
