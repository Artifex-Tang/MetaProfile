"""分析层三个端点（扫描监测 / 新技术发现 / 选题服务）的工具。"""
from __future__ import annotations

import pytest

from tests.mcp.conftest import call_tool, mcp_for


@pytest.fixture
def scan(fake_client):
    return mcp_for("scan-monitor", fake_client), fake_client


@pytest.fixture
def discovery(fake_client):
    return mcp_for("new-tech-discovery", fake_client), fake_client


@pytest.fixture
def topic(fake_client):
    return mcp_for("topic-selection", fake_client), fake_client


# ── 扫描监测 ────────────────────────────────────────────────


async def test_list_frontier_tech_defaults(scan):
    mcp, client = scan

    await call_tool(mcp, "list_frontier_tech", {})

    assert client.last["method"] == "GET"
    assert client.last["path"] == "/frontier-tech/list"
    assert client.last["params"] == {"page": 1, "page_size": 20}


async def test_list_frontier_tech_with_period(scan):
    mcp, client = scan

    await call_tool(
        mcp, "list_frontier_tech", {"period_from": "2026-01-01", "period_to": "2026-03-31"}
    )

    assert client.last["params"]["period_from"] == "2026-01-01"
    assert client.last["params"]["period_to"] == "2026-03-31"


async def test_alerts_is_a_separate_tool(scan):
    """预警和前沿技术列表响应结构不同，拆成两个工具而不是靠 flag 切换。"""
    mcp, client = scan

    await call_tool(mcp, "list_frontier_alerts", {"severity": "critical", "limit": 10})

    assert client.last["path"] == "/frontier-tech/alerts"
    assert client.last["params"] == {"severity": "critical", "limit": 10}


async def test_alerts_omits_none_severity(scan):
    mcp, client = scan

    await call_tool(mcp, "list_frontier_alerts", {})

    assert client.last["params"] == {"limit": 50}


async def test_get_frontier_tech(scan):
    mcp, client = scan

    await call_tool(mcp, "get_frontier_tech", {"tech_id": "F1"})

    assert client.last == {"method": "GET", "path": "/frontier-tech/F1", "params": None}


# ── 新技术发现 ──────────────────────────────────────────────


async def test_list_new_tech_defaults(discovery):
    mcp, client = discovery

    await call_tool(mcp, "list_new_tech", {})

    assert client.last["path"] == "/new-tech/list"
    assert client.last["params"] == {"min_strength": 0.0, "page": 1, "page_size": 20}


async def test_list_new_tech_filters(discovery):
    mcp, client = discovery

    await call_tool(
        mcp, "list_new_tech", {"domain": "材料", "period": "2026Q1", "min_strength": 0.6}
    )

    params = client.last["params"]
    assert params["domain"] == "材料"
    assert params["period"] == "2026Q1"
    assert params["min_strength"] == 0.6


async def test_list_tech_signals_defaults(discovery):
    mcp, client = discovery

    await call_tool(mcp, "list_tech_signals", {})

    assert client.last["path"] == "/new-tech/signals"
    assert client.last["params"] == {"min_strength": 0.0, "page": 1, "page_size": 50}


async def test_get_signal_network(discovery):
    mcp, client = discovery

    await call_tool(mcp, "get_signal_network", {"signal_id": "S3"})

    assert client.last["path"] == "/new-tech/signals/S3/network"


# ── 选题服务 ────────────────────────────────────────────────


async def test_list_topics_defaults(topic):
    mcp, client = topic

    await call_tool(mcp, "list_topics", {})

    assert client.last["path"] == "/topics/list"
    assert client.last["params"] == {"min_score": 0.0, "page": 1, "page_size": 20}


async def test_list_topics_filters(topic):
    mcp, client = topic

    await call_tool(mcp, "list_topics", {"period": "2026Q1", "min_score": 0.8})

    assert client.last["params"]["period"] == "2026Q1"
    assert client.last["params"]["min_score"] == 0.8


async def test_get_topic(topic):
    mcp, client = topic

    await call_tool(mcp, "get_topic", {"topic_id": "TP9"})

    assert client.last == {"method": "GET", "path": "/topics/TP9", "params": None}
