"""
单元测试：foundation/collectors

全部 mock HTTP，不发真实请求。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from metaprofile.foundation.collectors.base import (
    AbstractCollector,
    CollectError,
    CollectQuery,
    RawDocument,
)
from metaprofile.foundation.collectors.patent_cnipa import CNIPACollector
from metaprofile.foundation.collectors.paper_wos import WoSCollector
from metaprofile.foundation.collectors.project_nsfc import NSFCCollector
from metaprofile.foundation.collectors.enterprise_tianyancha import TianyanchaColl
from metaprofile.foundation.collectors.policy_gov import PolicyGovCollector


# ─── 测试辅助 ────────────────────────────────────────────────────────────────

def make_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("POST", "http://test"),
    )


def make_html_response(html: str, url: str = "http://test") -> httpx.Response:
    return httpx.Response(
        status_code=200,
        text=html,
        request=httpx.Request("GET", url),
    )


# ─── CollectQuery ────────────────────────────────────────────────────────────

def test_collect_query_defaults():
    q = CollectQuery(keywords=["量子计算"])
    assert q.max_results == 100
    assert q.date_from is None


def test_collect_query_requires_keywords():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CollectQuery(keywords=[])


def test_collect_query_max_results_bounds():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CollectQuery(keywords=["X"], max_results=0)
    with pytest.raises(ValidationError):
        CollectQuery(keywords=["X"], max_results=99999)


# ─── RawDocument ────────────────────────────────────────────────────────────

def test_raw_document_collected_at_auto():
    doc = RawDocument(source="cnipa", doc_type="patent", raw_id="CN123")
    assert doc.collected_at is not None
    assert doc.lang == "zh"


def test_raw_document_extra_field_forbidden():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RawDocument(source="x", doc_type="y", raw_id="z", nonexistent_field="v")


# ─── CNIPACollector ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cnipa_collect_yields_docs():
    mock_resp = make_response({
        "data": {
            "hits": [
                {"ANE": "CN202310001234.1", "TI": "量子纠错方法", "AB": "摘要内容"},
                {"ANE": "CN202310005678.2", "TI": "量子比特控制"},
            ]
        }
    })

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    collector = CNIPACollector(client=mock_client)
    query = CollectQuery(keywords=["量子纠错"], max_results=2)

    docs = []
    async for doc in collector.collect(query):
        docs.append(doc)

    assert len(docs) == 2
    assert docs[0].source == "cnipa"
    assert docs[0].doc_type == "patent"
    assert docs[0].raw_id == "CN202310001234.1"
    assert docs[0].title == "量子纠错方法"


@pytest.mark.asyncio
async def test_cnipa_collect_empty_stops():
    mock_resp = make_response({"data": {"hits": []}})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    collector = CNIPACollector(client=mock_client)
    docs = []
    async for doc in collector.collect(CollectQuery(keywords=["不存在关键词"])):
        docs.append(doc)

    assert docs == []


@pytest.mark.asyncio
async def test_cnipa_collect_respects_max_results():
    hits = [{"ANE": f"CN{i:010d}", "TI": f"专利{i}"} for i in range(50)]
    mock_resp = make_response({"data": {"hits": hits}})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    collector = CNIPACollector(client=mock_client)
    docs = []
    async for doc in collector.collect(CollectQuery(keywords=["量子"], max_results=5)):
        docs.append(doc)

    assert len(docs) == 5


@pytest.mark.asyncio
async def test_cnipa_get_by_id():
    mock_resp = make_response({
        "data": {"ANE": "CN202310001234.1", "TI": "量子纠错方法", "AB": "摘要"}
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    collector = CNIPACollector(client=mock_client)
    doc = await collector.get_by_id("CN202310001234.1")

    assert doc is not None
    assert doc.raw_id == "CN202310001234.1"
    assert doc.title == "量子纠错方法"


@pytest.mark.asyncio
async def test_cnipa_get_by_id_not_found():
    mock_resp = make_response({"data": None})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    collector = CNIPACollector(client=mock_client)
    doc = await collector.get_by_id("NOT_EXIST")
    assert doc is None


# ─── WoSCollector ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wos_collect_parses_title_dict():
    mock_resp = make_response({
        "hits": [
            {
                "uid": "WOS:000001",
                "title": {"value": "Quantum Error Correction"},
                "sourceTitle": "Nature",
            }
        ],
        "metadata": {"total": 1},
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    collector = WoSCollector(client=mock_client)
    docs = []
    async for doc in collector.collect(CollectQuery(keywords=["quantum error correction"])):
        docs.append(doc)

    assert len(docs) == 1
    assert docs[0].title == "Quantum Error Correction"
    assert docs[0].lang == "en"


# ─── NSFCCollector ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nsfc_collect_yields_projects():
    mock_resp = make_response({
        "result": {
            "data": [
                {"pjNo": "62271234", "pjName": "量子计算关键技术研究", "pi": "张三"},
            ],
            "total": 1,
        }
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    collector = NSFCCollector(client=mock_client)
    docs = []
    async for doc in collector.collect(CollectQuery(keywords=["量子计算"])):
        docs.append(doc)

    assert len(docs) == 1
    assert docs[0].source == "nsfc"
    assert docs[0].doc_type == "project"
    assert docs[0].raw_id == "62271234"


# ─── TianyanchaColl ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tianyancha_collect_ok():
    mock_resp = make_response({
        "state": "ok",
        "data": {
            "items": [
                {"id": 123456, "name": "量子计算科技有限公司"},
            ]
        },
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    collector = TianyanchaColl(client=mock_client)
    docs = []
    async for doc in collector.collect(CollectQuery(keywords=["量子计算"])):
        docs.append(doc)

    assert len(docs) == 1
    assert docs[0].raw_id == "123456"
    assert docs[0].title == "量子计算科技有限公司"


@pytest.mark.asyncio
async def test_tianyancha_api_error_skips():
    mock_resp = make_response({"state": "error", "message": "鉴权失败"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    collector = TianyanchaColl(client=mock_client)
    docs = []
    async for doc in collector.collect(CollectQuery(keywords=["X"])):
        docs.append(doc)
    assert docs == []


# ─── PolicyGovCollector ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_policy_gov_collect():
    mock_resp = make_response({
        "searchVO": {
            "total": 1,
            "categoryList": [{
                "listVO": [
                    {
                        "title": "关于推进量子信息技术发展的指导意见",
                        "url": "https://www.gov.cn/zhengce/2023-06/15/content_5741234.htm",
                        "publishTime": "2023-06-15",
                    }
                ]
            }],
        }
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    collector = PolicyGovCollector(client=mock_client)
    docs = []
    async for doc in collector.collect(CollectQuery(keywords=["量子信息"])):
        docs.append(doc)

    assert len(docs) == 1
    assert docs[0].source == "policy_gov"
    assert docs[0].doc_type == "policy"
    assert "量子信息" in docs[0].title
