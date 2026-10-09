"""分析层 MCP 工具：扫描监测 / 新技术发现 / 选题服务，各自独立成服务。

只暴露读接口：scan / verify / generate / feedback 依赖 celery worker 与 LLM，
只读云上部署已裁掉这两者，暴露出去只会让模型反复撞 503/超时。
"""
from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from metaprofile.mcp_server.api_client import BackendClient

Severity = Literal["info", "warn", "critical"]

SCAN_TOOL_NAMES: tuple[str, ...] = (
    "list_frontier_tech",
    "list_frontier_alerts",
    "get_frontier_tech",
)
DISCOVERY_TOOL_NAMES: tuple[str, ...] = (
    "list_new_tech",
    "list_tech_signals",
    "get_signal_network",
)
TOPIC_TOOL_NAMES: tuple[str, ...] = ("list_topics", "get_topic")


def register_scan_tools(mcp: FastMCP, client: BackendClient) -> None:
    """扫描监测工具（前沿技术列表 / 预警 / 详情）。"""

    @mcp.tool(
        description=(
            "列出扫描监测发现的前沿技术，按时间窗口分页。\n"
            "每项含五维信号得分与 TRL 成熟度标注。日期格式 YYYY-MM-DD。"
        )
    )
    async def list_frontier_tech(
        period_from: str | None = None,
        period_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Any:
        return await client.get(
            "/frontier-tech/list",
            params={
                "period_from": period_from,
                "period_to": period_to,
                "page": page,
                "page_size": page_size,
            },
        )

    @mcp.tool(
        description=(
            "列出扫描监测触发的预警记录（与前沿技术列表结构不同，含 severity 与触发原因）。\n"
            "severity 取 info / warn / critical，不传则返回全部等级。"
        )
    )
    async def list_frontier_alerts(
        severity: Severity | None = None, limit: int = 50
    ) -> Any:
        return await client.get(
            "/frontier-tech/alerts", params={"severity": severity, "limit": limit}
        )

    @mcp.tool(
        description=(
            "查询单条前沿技术详情：五维信号分项得分、LLM 验证证据、TRL 成熟度标注。"
        )
    )
    async def get_frontier_tech(tech_id: str) -> Any:
        return await client.get(f"/frontier-tech/{tech_id}")

    _ = (list_frontier_tech, list_frontier_alerts, get_frontier_tech)


def register_discovery_tools(mcp: FastMCP, client: BackendClient) -> None:
    """新技术发现工具（已聚合技术条目 / 原始弱信号 / 信号关联网络）。"""

    @mcp.tool(
        description=(
            "列出新技术发现结果（已聚合成技术条目的弱信号）。\n"
            "period 形如 2026Q1；min_strength 取 0-1，调高可只看强信号。\n"
            "想看未聚合的原始弱信号用 list_tech_signals。"
        )
    )
    async def list_new_tech(
        domain: str | None = None,
        period: str | None = None,
        min_strength: float = 0.0,
        page: int = 1,
        page_size: int = 20,
    ) -> Any:
        return await client.get(
            "/new-tech/list",
            params={
                "domain": domain,
                "period": period,
                "min_strength": min_strength,
                "page": page,
                "page_size": page_size,
            },
        )

    @mcp.tool(
        description=(
            "列出原始弱信号（尚未聚合成技术条目的碎片化情报线索）。\n"
            "min_strength 取 0-1；period_from 格式 YYYY-MM-DD。\n"
            "每条信号可再用 get_signal_network 展开它的关联网络。"
        )
    )
    async def list_tech_signals(
        domain: str | None = None,
        min_strength: float = 0.0,
        period_from: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Any:
        return await client.get(
            "/new-tech/signals",
            params={
                "domain": domain,
                "min_strength": min_strength,
                "period_from": period_from,
                "page": page,
                "page_size": page_size,
            },
        )

    @mcp.tool(
        description=(
            "查询某条弱信号的关联网络：节点为相关技术/机构/人物，边为共现/引用/资助等。"
        )
    )
    async def get_signal_network(signal_id: str) -> Any:
        return await client.get(f"/new-tech/signals/{signal_id}/network")

    _ = (list_new_tech, list_tech_signals, get_signal_network)


def register_topic_tools(mcp: FastMCP, client: BackendClient) -> None:
    """选题服务工具（候选选题列表 / 详情）。"""

    @mcp.tool(
        description=(
            "列出选题服务产出的候选选题，按综合得分排序。\n"
            "period 形如 2026Q1；min_score 取 0-1，调高可只看高分选题。"
        )
    )
    async def list_topics(
        period: str | None = None,
        min_score: float = 0.0,
        page: int = 1,
        page_size: int = 20,
    ) -> Any:
        return await client.get(
            "/topics/list",
            params={
                "period": period,
                "min_score": min_score,
                "page": page,
                "page_size": page_size,
            },
        )

    @mcp.tool(
        description=(
            "查询单个选题详情：5 策略分项得分、LLM 评审 4 维度评分、关联前沿技术与政策。"
        )
    )
    async def get_topic(topic_id: str) -> Any:
        return await client.get(f"/topics/{topic_id}")

    _ = (list_topics, get_topic)
