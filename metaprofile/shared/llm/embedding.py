"""
BGE Embedding 客户端。

通过 LiteLLM Proxy 或独立 Xinference 实例提供 embedding 服务。
"""
from __future__ import annotations

import httpx
import structlog

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


class EmbeddingClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=settings.llm.proxy_base_url,
            headers={"Authorization": f"Bearer {settings.llm.proxy_api_key}"},
            timeout=settings.llm.timeout_seconds,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成 Embedding。返回与 texts 顺序对应的向量列表。"""
        if not texts:
            return []
        resp = await self._client.post(
            "/v1/embeddings",
            json={"model": settings.llm.embedding_model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        return [d["embedding"] for d in data["data"]]

    async def embed_one(self, text: str) -> list[float]:
        result = await self.embed([text])
        return result[0]

    async def aclose(self) -> None:
        await self._client.aclose()


_default_client: EmbeddingClient | None = None


def get_default_embedding_client() -> EmbeddingClient:
    global _default_client
    if _default_client is None:
        _default_client = EmbeddingClient()
    return _default_client
