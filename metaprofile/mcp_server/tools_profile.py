"""画像类 MCP 工具（技术 / 项目 / 机构 / 人员各自独立成服务）。

四类画像的 REST 接口完全同构，只有路径段和请求体字段名带类型前缀
（tech_domain / org_ids ...）。这里把类型绑定在服务实例上，而不是做成工具参数，
这样每个 MCP 端点只暴露自己那一类的工具，客户端挂哪个就只看到哪个。

注意：工具描述一律走 @mcp.tool(description=...)，不要写成 f-string 文档字符串——
带 f 前缀的三引号串作为函数首个语句不会成为 __doc__，描述会静默丢失。
"""
from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from metaprofile.mcp_server.api_client import BackendClient

ProfileType = Literal["tech", "project", "org", "person"]
Viewpoint = Literal["evolve", "prereq"]

TYPE_LABEL: dict[str, str] = {
    "tech": "技术",
    "project": "项目",
    "org": "机构",
    "person": "人员",
}

PROFILE_TOOL_NAMES: tuple[str, ...] = (
    "search_profiles",
    "get_profile",
    "batch_get_profiles",
    "get_profile_stats",
    "list_profile_changes",
    "get_relations",
    "find_relation_path",
)
TECH_ONLY_TOOL_NAMES: tuple[str, ...] = ("get_tech_relation",)


def tool_names_for(profile_type: str) -> tuple[str, ...]:
    """某类画像服务暴露的工具名（技术类多一个演进关系工具）。"""
    if profile_type == "tech":
        return PROFILE_TOOL_NAMES + TECH_ONLY_TOOL_NAMES
    return PROFILE_TOOL_NAMES


def register_profile_tools(
    mcp: FastMCP, client: BackendClient, profile_type: ProfileType
) -> None:
    """把某一类画像的工具注册到 mcp 实例上。"""
    t = profile_type
    label = TYPE_LABEL[t]

    @mcp.tool(
        description=(
            f"按关键词/领域/时间窗口搜索{label}画像，返回分页命中列表。\n"
            f"这是按名字或主题找{label}的首选入口；拿到 ID 后再用 get_profile 取详情。\n"
            'domain 传领域名列表（如 ["人工智能","新材料"]），日期格式 YYYY-MM-DD。'
        )
    )
    async def search_profiles(
        keyword: str | None = None,
        domain: list[str] | None = None,
        invention_date_from: str | None = None,
        invention_date_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Any:
        body: dict[str, Any] = {"page": page, "page_size": page_size}
        if keyword is not None:
            body["keyword"] = keyword
        if domain is not None:
            # SearchRequest 用 extra="forbid"，字段名必须是 {type}_domain
            body[f"{t}_domain"] = domain
        if invention_date_from is not None:
            body["invention_date_from"] = invention_date_from
        if invention_date_to is not None:
            body["invention_date_to"] = invention_date_to
        return await client.post(f"/profile/{t}/search", json_body=body)

    @mcp.tool(
        description=(
            f"按 ID 查询单个{label}画像的完整详情"
            "（基础字段 + 质量评分 + 来源溯源）。"
        )
    )
    async def get_profile(profile_id: str) -> Any:
        return await client.get(f"/profile/{t}/{profile_id}")

    @mcp.tool(
        description=(
            f"按 ID 列表批量取{label}画像详情（最多 100 个），比逐个 get_profile 快得多。\n"
            "典型用法：get_relations 拿到一批关联对象 ID 后一次性取回它们的详情。"
        )
    )
    async def batch_get_profiles(profile_ids: list[str]) -> Any:
        return await client.post(
            f"/profile/{t}/batch", json_body={f"{t}_ids": profile_ids}
        )

    @mcp.tool(
        description=(
            f"查询{label}画像的综合统计："
            "总量、新增量、领域分布、完整度分布、LLM 贡献度。\n"
            f'回答"库里有多少{label}画像""哪个领域覆盖最全"这类问题用它，不要去翻列表数。'
        )
    )
    async def get_profile_stats() -> Any:
        return await client.get(f"/stats/{t}")

    @mcp.tool(
        description=(
            f"查询指定时段内{label}画像的字段级变更记录（谁在什么时候改了哪个字段）。\n"
            "since/until 用 ISO 时间格式，如 2026-01-01T00:00:00。since 必填。"
        )
    )
    async def list_profile_changes(
        since: str, until: str | None = None, limit: int = 100
    ) -> Any:
        return await client.get(
            f"/profile/{t}/changes",
            params={"since": since, "until": until, "limit": limit},
        )

    @mcp.tool(
        description=(
            f"查询某个{label}的全部关联对象（跨类型：技术↔机构↔人员↔项目）。\n"
            "relation_type 可选，用于只看某一类关系（如 COOPERATE / RESEARCH）。"
        )
    )
    async def get_relations(
        profile_id: str, relation_type: str | None = None, limit: int = 100
    ) -> Any:
        return await client.get(
            f"/relation/{t}/{profile_id}",
            params={"relation_type": relation_type, "limit": limit},
        )

    @mcp.tool(
        description=(
            '查询两个实体之间的最短关联路径，用于解释"他俩是怎么扯上关系的"。\n'
            f"from_id 是{label}的 ID；路径中间节点与终点可以是任意类型。"
        )
    )
    async def find_relation_path(
        from_id: str, to_id: str, max_depth: int = 4
    ) -> Any:
        return await client.post(
            f"/relation/{t}/path",
            json_body={"from_id": from_id, "to_id": to_id, "max_depth": max_depth},
        )

    registered = [
        search_profiles,
        get_profile,
        batch_get_profiles,
        get_profile_stats,
        list_profile_changes,
        get_relations,
        find_relation_path,
    ]

    if t == "tech":

        @mcp.tool(
            description=(
                "查询技术之间的演进关系图（技术画像专有）。\n"
                "viewpoint=evolve 看这项技术往后演进出了什么；"
                "viewpoint=prereq 看它依赖哪些前置技术。depth 取 1-4。"
            )
        )
        async def get_tech_relation(
            tech_id: str, viewpoint: Viewpoint = "evolve", depth: int = 4
        ) -> Any:
            return await client.get(
                f"/relation/tech/{tech_id}/tech-relation",
                params={"viewpoint": viewpoint, "depth": depth},
            )

        registered.append(get_tech_relation)

    _ = registered
