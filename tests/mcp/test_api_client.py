"""BackendClient 测试：路径拼接、None 参数剔除、错误映射。"""
from __future__ import annotations

import httpx
import pytest

from metaprofile.mcp_server.api_client import BackendClient, BackendError


def _client(handler) -> BackendClient:
    transport = httpx.MockTransport(handler)
    return BackendClient(
        base_url="http://backend:8000/api/v1",
        http_client=httpx.AsyncClient(transport=transport),
    )


async def test_get_prefixes_base_url():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"id": "T1"})

    result = await _client(handler).get("/profile/tech/T1")

    assert seen["url"] == "http://backend:8000/api/v1/profile/tech/T1"
    assert result == {"id": "T1"}


async def test_get_drops_none_params():
    """httpx 会把 None 编码成空串，后端 date 解析会 422，必须先剔除。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["query"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    await _client(handler).get("/new-tech/list", params={"domain": None, "page": 1})

    assert seen["query"] == {"page": "1"}


async def test_post_sends_json_body():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"items": []})

    await _client(handler).post("/profile/org/search", json_body={"keyword": "航天"})

    assert '"keyword"' in seen["body"]
    assert "航天" in seen["body"]


async def test_404_raises_backend_error_with_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "tech_id=X not found"})

    with pytest.raises(BackendError) as exc:
        await _client(handler).get("/profile/tech/X")

    assert exc.value.status_code == 404
    assert "not found" in str(exc.value)


async def test_503_readonly_gives_actionable_message():
    """只读熔断是运行时最常见的失败，报错必须让模型看懂而不是重试。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "disabled in readonly mode"})

    with pytest.raises(BackendError) as exc:
        await _client(handler).post("/profile/tech/T1/enrich")

    assert exc.value.status_code == 503
    assert "readonly" in str(exc.value)


async def test_connection_failure_raises_backend_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(BackendError) as exc:
        await _client(handler).get("/stats/tech")

    assert exc.value.status_code == 0
    assert "connection refused" in str(exc.value)


async def test_non_json_response_raises_backend_error():
    """打到 nginx SPA fallback 时会拿到 HTML，这是配错前缀的典型症状。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<!doctype html><html></html>")

    with pytest.raises(BackendError) as exc:
        await _client(handler).get("/stats/tech")

    assert "JSON" in str(exc.value)
