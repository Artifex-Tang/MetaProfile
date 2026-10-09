"""7 个 MCP 服务的定义表。

一个工具一个 MCP 端点，路径 /mcp/<slug>，客户端按需只挂自己要的那几个。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from mcp.server.fastmcp import FastMCP

from metaprofile.mcp_server.api_client import BackendClient
from metaprofile.mcp_server.tools_analysis import (
    DISCOVERY_TOOL_NAMES,
    SCAN_TOOL_NAMES,
    TOPIC_TOOL_NAMES,
    register_discovery_tools,
    register_scan_tools,
    register_topic_tools,
)
from metaprofile.mcp_server.tools_profile import (
    register_profile_tools,
    tool_names_for,
)

Registrar = Callable[[FastMCP, BackendClient], None]


@dataclass(frozen=True)
class McpService:
    """一个 MCP 端点的完整定义。"""

    slug: str  # URL 路径段：/mcp/<slug>
    key: str  # 客户端配置里 mcpServers 下的键名
    title: str  # 中文名（导出配置时作为标题）
    instructions: str
    tool_names: tuple[str, ...]
    register: Registrar

    @property
    def path(self) -> str:
        return f"/mcp/{self.slug}"


_PROFILE_FLOW = (
    "典型检索路径：search_profiles 找到实体拿 ID → get_profile 取详情 → "
    "get_relations 看关联对象 → batch_get_profiles 批量取回关联对象详情 → "
    "find_relation_path 解释两者之间的关联链路。\n"
    "本服务全部为只读查询，不提供写入、导入或 LLM 补全能力。"
)


def _profile_service(slug: str, key: str, title: str, ptype: str, extra: str) -> McpService:
    return McpService(
        slug=slug,
        key=key,
        title=title,
        instructions=f"MetaProfile {title}。{extra}\n\n{_PROFILE_FLOW}",
        tool_names=tool_names_for(ptype),
        register=partial(register_profile_tools, profile_type=ptype),  # type: ignore[arg-type]
    )


SERVICES: tuple[McpService, ...] = (
    _profile_service(
        "tech-profile", "techProfile", "技术画像工具", "tech",
        "查询技术实体的画像详情、发展脉络、关联机构/人员/项目，以及技术之间的演进与前置关系。",
    ),
    _profile_service(
        "project-profile", "projectProfile", "项目画像工具", "project",
        "查询科研/工程项目的画像详情、目标进展与关联的技术、承研机构和参与人员。",
    ),
    _profile_service(
        "org-profile", "orgProfile", "机构画像工具", "org",
        "查询机构的画像详情、能力布局与关联的技术、项目和人员。",
    ),
    _profile_service(
        "person-profile", "personProfile", "人员画像工具", "person",
        "查询人员的画像详情、研究方向与关联的技术、项目和任职机构。",
    ),
    McpService(
        slug="scan-monitor",
        key="scanMonitor",
        title="扫描监测工具",
        instructions=(
            "MetaProfile 扫描监测工具。查询已发现的前沿技术、五维信号得分、"
            "TRL 成熟度标注与监测预警记录。\n"
            "本服务只读，不能触发新的扫描任务（依赖 LLM 与异步 worker，只读部署未启用）。"
        ),
        tool_names=SCAN_TOOL_NAMES,
        register=register_scan_tools,
    ),
    McpService(
        slug="new-tech-discovery",
        key="newTechDiscovery",
        title="新技术发现工具",
        instructions=(
            "MetaProfile 新技术发现工具。查询从碎片化情报中聚合出的新技术条目、"
            "原始弱信号，以及单条信号的关联网络。\n"
            "本服务只读，不能触发新的发现任务。"
        ),
        tool_names=DISCOVERY_TOOL_NAMES,
        register=register_discovery_tools,
    ),
    McpService(
        slug="topic-selection",
        key="topicSelection",
        title="选题服务工具",
        instructions=(
            "MetaProfile 选题服务工具。查询候选选题列表与单个选题的详情"
            "（5 策略分项得分、LLM 评审 4 维度评分、关联前沿技术与政策）。\n"
            "本服务只读，不能生成新选题，也不能提交反馈。"
        ),
        tool_names=TOPIC_TOOL_NAMES,
        register=register_topic_tools,
    ),
)

SERVICE_BY_SLUG: dict[str, McpService] = {s.slug: s for s in SERVICES}

# 全部端点合计暴露的工具数（8 + 7×3 + 3 + 3 + 2 = 37）
TOTAL_TOOL_COUNT: int = sum(len(s.tool_names) for s in SERVICES)
