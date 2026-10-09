"""挂载测试：7 个端点各自可达、不重定向、不遮蔽 REST 路由。"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from metaprofile.mcp_server.registry import SERVICES
from metaprofile.mcp_server.server import mcp_lifespan, mount_mcp

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
INIT_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "1.0"},
    },
}
SLUGS = [s.slug for s in SERVICES]


def build_app(servers, token: str | None = None) -> FastAPI:
    app = FastAPI(lifespan=mcp_lifespan(servers))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    mount_mcp(app, servers, token=token)  # 必须在 REST 路由之后
    return app


def parse_sse(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:") :].strip())
    return json.loads(text)


@pytest.mark.parametrize("slug", SLUGS)
def test_each_endpoint_completes_initialize(servers, slug):
    with TestClient(build_app(servers)) as client:
        r = client.post(f"/mcp/{slug}", headers=MCP_HEADERS, json=INIT_BODY)

    assert r.status_code == 200
    payload = parse_sse(r.text)
    expected_key = next(s.key for s in SERVICES if s.slug == slug)
    assert payload["result"]["serverInfo"]["name"] == expected_key


@pytest.mark.parametrize("slug", SLUGS)
def test_no_redirect_on_bare_path(servers, slug):
    """MCP 客户端普遍不跟随重定向；TestClient 默认跟随，必须显式关掉才抓得到。"""
    with TestClient(build_app(servers)) as client:
        r = client.post(
            f"/mcp/{slug}", headers=MCP_HEADERS, json=INIT_BODY, follow_redirects=False
        )

    assert r.status_code != 307, f"/mcp/{slug} 被重定向到 {r.headers.get('location')}"
    assert r.status_code == 200


@pytest.mark.parametrize("slug", SLUGS)
def test_each_endpoint_lists_only_its_own_tools(servers, slug):
    expected = {s for s in SERVICES if s.slug == slug}.pop()

    with TestClient(build_app(servers)) as client:
        client.post(f"/mcp/{slug}", headers=MCP_HEADERS, json=INIT_BODY)
        r = client.post(
            f"/mcp/{slug}",
            headers=MCP_HEADERS,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )

    names = {t["name"] for t in parse_sse(r.text)["result"]["tools"]}
    assert names == set(expected.tool_names)


def test_unknown_slug_is_404(servers):
    with TestClient(build_app(servers)) as client:
        r = client.post("/mcp/no-such-tool", headers=MCP_HEADERS, json=INIT_BODY)

    assert r.status_code == 404


def test_mount_does_not_shadow_existing_routes(servers):
    """挂在 "/" 是兜底项，不能吃掉先注册的 REST 路由。"""
    with TestClient(build_app(servers)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/nope").status_code == 404
