"""客户端配置导出：形态是对外交付物，必须稳定。"""
from __future__ import annotations

import json

from metaprofile.mcp_server.config_export import (
    build_client_config,
    render_all,
    render_combined,
    render_reference,
)
from metaprofile.mcp_server.registry import SERVICE_BY_SLUG, SERVICES

BASE = "http://47.120.41.179"


def test_single_config_shape_with_token():
    cfg = build_client_config(SERVICE_BY_SLUG["tech-profile"], BASE, "mp_abc")

    assert cfg == {
        "mcpServers": {
            "techProfile": {
                "url": "http://47.120.41.179/mcp/tech-profile",
                "headers": {"Authorization": "Bearer mp_abc"},
            }
        }
    }


def test_config_omits_headers_without_token():
    cfg = build_client_config(SERVICE_BY_SLUG["scan-monitor"], BASE)

    assert cfg["mcpServers"]["scanMonitor"] == {
        "url": "http://47.120.41.179/mcp/scan-monitor"
    }


def test_base_url_trailing_slash_does_not_double_up():
    cfg = build_client_config(SERVICE_BY_SLUG["org-profile"], BASE + "/")

    assert cfg["mcpServers"]["orgProfile"]["url"] == f"{BASE}/mcp/org-profile"


def test_https_base_url():
    cfg = build_client_config(SERVICE_BY_SLUG["topic-selection"], "https://mp.example.com")

    assert cfg["mcpServers"]["topicSelection"]["url"] == (
        "https://mp.example.com/mcp/topic-selection"
    )


def test_render_all_has_seven_numbered_blocks():
    text = render_all(BASE, "mp_abc")

    for i, service in enumerate(SERVICES, start=1):
        assert f"{i}，{service.title}" in text
    assert text.count('"mcpServers"') == 7


def test_render_all_keeps_chinese_unescaped():
    """ensure_ascii=False：贴出去要是可读中文，不是 \\uXXXX。"""
    text = render_all(BASE, "mp_abc")

    assert "技术画像工具" in text
    assert "\\u" not in text


def test_render_combined_contains_all_seven_keys():
    cfg = json.loads(render_combined(BASE, "mp_abc"))

    assert set(cfg["mcpServers"]) == {s.key for s in SERVICES}


def test_render_combined_urls_are_distinct():
    cfg = json.loads(render_combined(BASE, "mp_abc"))
    urls = [v["url"] for v in cfg["mcpServers"].values()]

    assert len(set(urls)) == 7


def test_reference_is_bracket_wrapped():
    text = render_reference(BASE, "mp_abc")
    assert text.startswith("[")
    assert text.rstrip().endswith("]")


def test_reference_json_is_zero_indent():
    text = render_reference(BASE, "mp_abc")
    assert '  "mcpServers"' not in text
    assert "\n\"url\":" in text


def test_reference_each_entry_complete():
    text = render_reference(BASE, "mp_abc")
    first = text.split("2，")[0].split("{", 1)[1].rsplit("}", 1)[0]
    cfg = json.loads("{" + first + "}")
    assert cfg["mcpServers"]["techProfile"]["url"].endswith("/mcp/tech-profile")
