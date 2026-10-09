"""导出 MCP 客户端配置（每个端点一段独立 JSON）。

输出形态对齐常见 MCP hub 的分发格式：一个工具一段配置，用户按需粘贴。
"""
from __future__ import annotations

import json

from metaprofile.mcp_server.registry import SERVICES, McpService


def build_client_config(
    service: McpService, base_url: str, token: str | None = None
) -> dict[str, object]:
    """单个端点的客户端配置字典。"""
    entry: dict[str, object] = {"url": f"{base_url.rstrip('/')}{service.path}"}
    if token:
        entry["headers"] = {"Authorization": f"Bearer {token}"}
    return {"mcpServers": {service.key: entry}}


def render_all(base_url: str, token: str | None = None) -> str:
    """渲染成带中文标题的分段文本，可直接贴给使用方。"""
    blocks: list[str] = []
    for i, service in enumerate(SERVICES, start=1):
        cfg = json.dumps(
            build_client_config(service, base_url, token),
            ensure_ascii=False,
            indent=2,
        )
        blocks.append(f"{i}，{service.title}\n{cfg}")
    return "\n\n".join(blocks)


def render_reference(base_url: str, token: str | None = None) -> str:
    """渲染成参考格式：`[ 序号，标题 + flush-left 无缩进 JSON ... ]`。

    对齐 mcphub 那种分发文本：整体用方括号包起来，每项是「序号，中文标题」
    换行后跟一段零缩进的 JSON 对象（每层都顶格）。
    这是文本格式而非合法 JSON，给人看 / 粘贴用，不保证可整体解析。
    """
    blocks: list[str] = []
    for i, service in enumerate(SERVICES, start=1):
        cfg = json.dumps(
            build_client_config(service, base_url, token),
            ensure_ascii=False,
            indent=0,
        )
        blocks.append(f"{i}，{service.title}\n{cfg}")
    return "[" + "\n".join(blocks) + "\n]"


def render_combined(base_url: str, token: str | None = None) -> str:
    """渲染成一份合并配置（一次挂全部 7 个端点）。"""
    servers: dict[str, object] = {}
    for service in SERVICES:
        servers.update(build_client_config(service, base_url, token)["mcpServers"])  # type: ignore[arg-type]
    return json.dumps({"mcpServers": servers}, ensure_ascii=False, indent=2)
