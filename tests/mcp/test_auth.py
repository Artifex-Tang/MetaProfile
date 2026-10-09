"""Bearer token 鉴权：7 个端点全覆盖，未配置 token 时放行。"""
from __future__ import annotations

import os
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from metaprofile.mcp_server.registry import SERVICES
from metaprofile.mcp_server.server import auth_token_from_env
from tests.mcp.test_mount import INIT_BODY, MCP_HEADERS, build_app, parse_sse

TOKEN = "mp_secret_token"
SLUGS = [s.slug for s in SERVICES]


@pytest.mark.parametrize("slug", SLUGS)
def test_missing_token_is_401(servers, slug):
    with TestClient(build_app(servers, token=TOKEN)) as client:
        r = client.post(f"/mcp/{slug}", headers=MCP_HEADERS, json=INIT_BODY)

    assert r.status_code == 401
    assert "bearer" in r.headers.get("www-authenticate", "").lower()


@pytest.mark.parametrize("slug", SLUGS)
def test_correct_token_passes(servers, slug):
    headers = {**MCP_HEADERS, "Authorization": f"Bearer {TOKEN}"}

    with TestClient(build_app(servers, token=TOKEN)) as client:
        r = client.post(f"/mcp/{slug}", headers=headers, json=INIT_BODY)

    assert r.status_code == 200
    assert "serverInfo" in parse_sse(r.text)["result"]


def test_wrong_token_is_401(servers):
    headers = {**MCP_HEADERS, "Authorization": "Bearer wrong"}

    with TestClient(build_app(servers, token=TOKEN)) as client:
        r = client.post("/mcp/tech-profile", headers=headers, json=INIT_BODY)

    assert r.status_code == 401


def test_token_prefix_is_not_accepted(servers):
    """定长比较不能被前缀试探绕过。"""
    headers = {**MCP_HEADERS, "Authorization": f"Bearer {TOKEN[:5]}"}

    with TestClient(build_app(servers, token=TOKEN)) as client:
        r = client.post("/mcp/tech-profile", headers=headers, json=INIT_BODY)

    assert r.status_code == 401


def test_wrong_scheme_is_401(servers):
    headers = {**MCP_HEADERS, "Authorization": f"Basic {TOKEN}"}

    with TestClient(build_app(servers, token=TOKEN)) as client:
        r = client.post("/mcp/tech-profile", headers=headers, json=INIT_BODY)

    assert r.status_code == 401


def test_no_token_configured_allows_everything(servers):
    with TestClient(build_app(servers, token=None)) as client:
        r = client.post("/mcp/tech-profile", headers=MCP_HEADERS, json=INIT_BODY)

    assert r.status_code == 200


def test_auth_does_not_affect_rest_routes(servers):
    """鉴权只包 MCP 子应用，REST 路由不受影响。"""
    with TestClient(build_app(servers, token=TOKEN)) as client:
        assert client.get("/health").status_code == 200


def test_auth_token_from_env_unset():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MCP_AUTH_TOKEN", None)
        assert auth_token_from_env() is None


def test_auth_token_from_env_blank_is_none():
    with mock.patch.dict(os.environ, {"MCP_AUTH_TOKEN": "   "}):
        assert auth_token_from_env() is None


def test_auth_token_from_env_reads_value():
    with mock.patch.dict(os.environ, {"MCP_AUTH_TOKEN": " abc "}):
        assert auth_token_from_env() == "abc"
