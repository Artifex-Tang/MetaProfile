"""真实 backend 应用上的 MCP 挂载冒烟测试。

只查路由表与装配，不发 DB 请求。
"""
from __future__ import annotations

from starlette.routing import Mount

from metaprofile.mcp_server.registry import SERVICES


def _app():
    from metaprofile.backend.main import app

    return app


def test_mcp_mount_is_registered_last():
    """MCP 挂在 "/"(兜底)，必须是最后一条路由，否则会吃掉全部 REST 路由。"""
    routes = _app().routes

    assert isinstance(routes[-1], Mount), "最后一条路由不是 Mount"
    assert routes[-1].path == "", 'MCP 应挂在 "/"(Starlette 归一化为 "")'
    assert not [r for r in routes[:-1] if isinstance(r, Mount) and r.path == ""], (
        "存在更早注册的根 Mount，会遮蔽后续路由"
    )


def test_rest_routes_survive_mcp_mount():
    paths = {getattr(r, "path", None) for r in _app().routes}

    assert "/health" in paths
    assert "/api/v1/profile/tech/{tech_id}" in paths
    assert "/api/v1/stats/tech" in paths


def test_seven_mcp_servers_built():
    from metaprofile.backend.main import mcp_servers

    assert set(mcp_servers) == {s.slug for s in SERVICES}


def test_each_server_registers_declared_tool_count():
    from metaprofile.backend.main import mcp_servers

    for service in SERVICES:
        actual = len(mcp_servers[service.slug]._tool_manager.list_tools())
        assert actual == len(service.tool_names), f"{service.slug} 工具数不符"
