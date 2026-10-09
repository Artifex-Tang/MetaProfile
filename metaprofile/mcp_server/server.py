"""7 个 MCP 端点的装配与挂载。

每个工具一个端点：/mcp/tech-profile、/mcp/scan-monitor …
全部挂在 backend 同一个 FastAPI 应用里，经 nginx :80/:443 暴露，不额外开端口。
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from metaprofile.mcp_server.api_client import BackendClient
from metaprofile.mcp_server.auth import BearerAuthMiddleware
from metaprofile.mcp_server.registry import SERVICES, McpService

MCP_PREFIX = "/mcp"


def build_mcp(
    service: McpService,
    client: BackendClient,
    allowed_hosts: list[str] | None = None,
) -> FastMCP:
    """构造单个 MCP 端点。"""
    mcp = FastMCP(
        service.key,
        instructions=service.instructions,
        stateless_http=True,
        streamable_http_path=service.path,
        transport_security=_transport_security(allowed_hosts),
    )
    service.register(mcp, client)
    # session_manager 是 streamable_http_app() 里懒创建的，不先调一次的话
    # mcp_lifespan 访问 mcp.session_manager 会直接 RuntimeError。
    mcp.streamable_http_app()
    return mcp


def build_all(
    client: BackendClient, allowed_hosts: list[str] | None = None
) -> dict[str, FastMCP]:
    """按注册表构造全部 7 个端点，返回 {slug: FastMCP}。"""
    return {s.slug: build_mcp(s, client, allowed_hosts) for s in SERVICES}


def _transport_security(
    allowed_hosts: list[str] | None,
) -> TransportSecuritySettings:
    if not allowed_hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(allowed_hosts),
        allowed_origins=[f"https://{h}" for h in allowed_hosts]
        + [f"http://{h}" for h in allowed_hosts],
    )


def allowed_hosts_from_env() -> list[str] | None:
    """MCP_ALLOWED_HOSTS="a.com,b.com" → ["a.com","b.com"]；未设则 None（不校验）。"""
    raw = os.getenv("MCP_ALLOWED_HOSTS", "").strip()
    if not raw:
        return None
    return [h.strip() for h in raw.split(",") if h.strip()]


def auth_token_from_env() -> str | None:
    """MCP_AUTH_TOKEN；未设则 None（不鉴权）。"""
    return os.getenv("MCP_AUTH_TOKEN", "").strip() or None


def default_backend_client() -> BackendClient:
    """默认走回环访问同容器内的 backend。"""
    base_url = os.getenv("MCP_BACKEND_BASE_URL", "http://127.0.0.1:8000/api/v1")
    return BackendClient(base_url=base_url)


def mount_mcp(
    app: FastAPI, servers: dict[str, FastMCP], token: str | None = None
) -> None:
    """把全部 MCP 端点挂进 app（挂载点 "/"，各端点靠自身绝对路径区分）。

    为什么挂 "/" 而不是 "/mcp"：mount 到 "/mcp" 时 Starlette 的 Mount 正则是
    ``^/mcp(?P<path>/.*)$``，配合 Router 的 redirect_slashes 会把裸路径 307 走，
    而 MCP 客户端普遍不跟随重定向。这里把每个端点的完整路径（/mcp/<slug>）
    直接注册成路由，再整体挂在兜底位置。

    必须在全部 REST 路由注册完之后调用：Starlette 按注册顺序匹配，
    挂在 "/" 的 Mount 是兜底项，先注册会吃掉所有路由。
    """
    routes = [r for mcp in servers.values() for r in mcp.streamable_http_app().routes]
    combined = Starlette(routes=routes)
    app.mount("/", BearerAuthMiddleware(combined, token))


def mcp_lifespan(servers: dict[str, FastMCP]) -> Callable[[FastAPI], object]:
    """生成负责跑全部 MCP session manager 的 lifespan。

    Starlette 子应用被 mount 时其 lifespan 不会自动执行，session manager
    必须由父应用显式拉起，否则请求会报 task group not initialized。
    """

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for mcp in servers.values():
                await stack.enter_async_context(mcp.session_manager.run())
            yield

    return _lifespan
