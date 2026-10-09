"""MCP 工具层测试夹具：用假的后端客户端记录 HTTP 调用，不碰真实网络/数据库。"""
from __future__ import annotations

import json
from typing import Any

import pytest

from metaprofile.mcp_server.api_client import BackendClient, _drop_none
from metaprofile.mcp_server.registry import SERVICE_BY_SLUG
from metaprofile.mcp_server.server import build_all, build_mcp


class FakeBackendClient(BackendClient):
    """记录调用并返回预置响应的 BackendClient 替身。

    必须与真 BackendClient 行为一致（含 None 参数剔除），否则测试通过
    但线上把 None 编码成空串打给后端拿 422。
    """

    def __init__(self, response: Any = None) -> None:  # noqa: D107 — 不调用父类 __init__
        self.calls: list[dict[str, Any]] = []
        self.response = response if response is not None else {"ok": True}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append({"method": "GET", "path": path, "params": _drop_none(params)})
        return self.response

    async def post(self, path: str, json_body: dict[str, Any] | None = None) -> Any:
        self.calls.append({"method": "POST", "path": path, "json": json_body})
        return self.response

    async def aclose(self) -> None:
        return None

    @property
    def last(self) -> dict[str, Any]:
        return self.calls[-1]


@pytest.fixture
def fake_client() -> FakeBackendClient:
    return FakeBackendClient()


@pytest.fixture
def servers(fake_client: FakeBackendClient):
    """全部 7 个 MCP 端点，{slug: FastMCP}。"""
    return build_all(fake_client)


def mcp_for(slug: str, client: BackendClient):
    """单独构造某个端点，用于只关心一个服务的测试。"""
    return build_mcp(SERVICE_BY_SLUG[slug], client)


async def call_tool(mcp_server, name: str, args: dict[str, Any]) -> Any:
    """调用 MCP 工具并把返回内容解析回 python 对象。

    FastMCP 不同版本 call_tool 返回 list[ContentBlock] 或 (content, structured) 二元组，
    这里统一处理。
    """
    result = await mcp_server.call_tool(name, args)
    content = result[0] if isinstance(result, tuple) else result
    text = content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
