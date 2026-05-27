"""
Elasticsearch 8.x 异步客户端。

功能：文档 CRUD、全文检索、kNN 向量检索、批量写入。
"""
from __future__ import annotations

from typing import Any

import structlog
from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_client: AsyncElasticsearch | None = None


def get_es_client() -> AsyncElasticsearch:
    global _client
    if _client is None:
        kwargs: dict[str, Any] = {"hosts": settings.es.hosts}
        if settings.es.username and settings.es.password:
            kwargs["basic_auth"] = (settings.es.username, settings.es.password)
        _client = AsyncElasticsearch(**kwargs)
    return _client


class ESRepo:
    """Elasticsearch 操作封装。所有 index 名均通过参数传入，不硬编码。"""

    def __init__(self, client: AsyncElasticsearch | None = None) -> None:
        self._client = client or get_es_client()

    async def upsert(self, *, index: str, doc_id: str, body: dict[str, Any]) -> None:
        await self._client.index(index=index, id=doc_id, document=body)

    async def get(self, *, index: str, doc_id: str) -> dict[str, Any] | None:
        try:
            resp = await self._client.get(index=index, id=doc_id)
            return dict(resp["_source"])
        except NotFoundError:
            return None

    async def delete(self, *, index: str, doc_id: str) -> bool:
        try:
            await self._client.delete(index=index, id=doc_id)
            return True
        except NotFoundError:
            return False

    async def search(
        self,
        *,
        index: str,
        query: dict[str, Any],
        size: int = 10,
        from_: int = 0,
        source_includes: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "index": index,
            "query": query,
            "size": size,
            "from_": from_,
        }
        if source_includes:
            kwargs["source_includes"] = source_includes
        resp = await self._client.search(**kwargs)
        return [dict(hit["_source"]) for hit in resp["hits"]["hits"]]

    async def knn_search(
        self,
        *,
        index_alias: str,
        vector: list[float],
        field: str = "embedding",
        top_k: int = 20,
        num_candidates: int = 100,
        filter_query: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """ES 8.x kNN 向量检索。返回带 _score 的原始 hit 列表（含 _source）。"""
        knn_body: dict[str, Any] = {
            "field": field,
            "query_vector": vector,
            "k": top_k,
            "num_candidates": num_candidates,
        }
        if filter_query:
            knn_body["filter"] = filter_query

        resp = await self._client.search(index=index_alias, knn=knn_body, size=top_k)
        hits = resp["hits"]["hits"]
        # 注入 _score 到 _source 方便上层直接用
        result = []
        for hit in hits:
            doc = dict(hit["_source"])
            doc["_score"] = hit["_score"]
            doc["_id"] = hit["_id"]
            result.append(doc)
        return result

    async def bulk_upsert(
        self,
        *,
        index: str,
        docs: list[tuple[str, dict[str, Any]]],
    ) -> tuple[int, list[Any]]:
        """批量 upsert。docs 是 (doc_id, body) 列表。"""
        actions = [
            {"_op_type": "index", "_index": index, "_id": doc_id, **body}
            for doc_id, body in docs
        ]
        success, errors = await async_bulk(self._client, actions, raise_on_error=False)
        if errors:
            logger.warning("es_bulk_upsert_partial_errors", error_count=len(errors))
        return success, errors

    async def ensure_index(
        self,
        *,
        index: str,
        mapping: dict[str, Any],
        settings_body: dict[str, Any] | None = None,
    ) -> None:
        """创建索引（若不存在）。"""
        exists = await self._client.indices.exists(index=index)
        if exists.body:
            return
        body: dict[str, Any] = {"mappings": mapping}
        if settings_body:
            body["settings"] = settings_body
        await self._client.indices.create(index=index, body=body)
        logger.info("es_index_created", index=index)

    async def count(self, *, index: str, query: dict[str, Any] | None = None) -> int:
        kwargs: dict[str, Any] = {"index": index}
        if query:
            kwargs["query"] = query
        resp = await self._client.count(**kwargs)
        return int(resp["count"])
