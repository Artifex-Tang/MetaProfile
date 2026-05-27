"""
RAG 文档检索器。

为 LLM 字段补全提供支撑文档上下文：
1. 关键词全文检索（ES match query）
2. 向量 kNN 检索（若提供 embedding_client）
合并结果去重，按相关性排序，截断到 max_chars 以控制 prompt 大小。
"""
from __future__ import annotations

from dataclasses import dataclass

from metaprofile.shared.schemas.base import EntityType

_DEFAULT_TOP_K = 5
_DEFAULT_MAX_CHARS = 3000
_RAW_DOC_INDEX = "metaprofile_raw_docs"  # 清洗后原始文档索引


@dataclass
class RetrievedDoc:
    doc_id: str
    title: str
    snippet: str        # 截断后的文本摘要
    score: float
    source: str         # "keyword" | "vector"


class RAGRetriever:
    """
    双路检索器：keyword + (可选) vector。

    Args:
        es_repo: ESRepo 实例
        embedding_client: EmbeddingClient（可为 None，则跳过 kNN）
        raw_doc_index: 原始文档 ES 索引名
    """

    def __init__(
        self,
        es_repo: object,
        embedding_client: object | None = None,
        raw_doc_index: str = _RAW_DOC_INDEX,
    ) -> None:
        self._es = es_repo
        self._emb = embedding_client
        self._raw_index = raw_doc_index

    async def retrieve(
        self,
        *,
        entity_type: EntityType,
        query_text: str,
        top_k: int = _DEFAULT_TOP_K,
        max_chars: int = _DEFAULT_MAX_CHARS,
    ) -> list[RetrievedDoc]:
        """
        双路检索，合并去重，截断片段。

        Args:
            query_text: 实体名称 + 摘要拼接成的查询文本
            top_k: 每路检索数量
            max_chars: 每条文档 snippet 最大字符数

        Returns:
            去重后的检索结果列表（按 score 降序）
        """
        keyword_hits = await self._keyword_search(query_text, top_k)
        vector_hits: list[RetrievedDoc] = []

        if self._emb is not None:
            vector_hits = await self._vector_search(query_text, top_k)

        merged = _merge_hits(keyword_hits, vector_hits)
        for doc in merged:
            doc.snippet = doc.snippet[:max_chars]
        return merged

    async def _keyword_search(self, query: str, top_k: int) -> list[RetrievedDoc]:
        try:
            hits = await self._es.search(
                index=self._raw_index,
                query={
                    "multi_match": {
                        "query": query,
                        "fields": ["title^2", "abstract", "content"],
                        "type": "best_fields",
                    }
                },
                size=top_k,
            )
        except Exception:  # noqa: BLE001
            return []

        results = []
        for hit in hits:
            results.append(
                RetrievedDoc(
                    doc_id=hit.get("_id", ""),
                    title=hit.get("title", ""),
                    snippet=hit.get("abstract", "") or hit.get("content", "")[:500],
                    score=float(hit.get("_score", 0.0)),
                    source="keyword",
                )
            )
        return results

    async def _vector_search(self, query: str, top_k: int) -> list[RetrievedDoc]:
        try:
            vector = await self._emb.embed_one(query)
            hits = await self._es.knn_search(
                index_alias=self._raw_index,
                vector=vector,
                field="embedding",
                top_k=top_k,
            )
        except Exception:  # noqa: BLE001
            return []

        results = []
        for hit in hits:
            results.append(
                RetrievedDoc(
                    doc_id=hit.get("_id", ""),
                    title=hit.get("title", ""),
                    snippet=hit.get("abstract", "") or hit.get("content", "")[:500],
                    score=float(hit.get("_score", 0.0)),
                    source="vector",
                )
            )
        return results


def _merge_hits(
    keyword: list[RetrievedDoc],
    vector: list[RetrievedDoc],
) -> list[RetrievedDoc]:
    """Merge two hit lists, deduplicate by doc_id, keep highest score."""
    seen: dict[str, RetrievedDoc] = {}
    for doc in keyword + vector:
        key = doc.doc_id or doc.title
        if key not in seen or doc.score > seen[key].score:
            seen[key] = doc
    return sorted(seen.values(), key=lambda d: d.score, reverse=True)
