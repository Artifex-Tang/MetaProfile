"""
UIE (Universal Information Extraction) 推理客户端。

调用 PaddleNLP UIE 服务，支持 zero-shot 抽取（schema 驱动）。
相比 BERT-CRF 更灵活，但速度稍慢，两者互补。

推理服务接口约定（POST /uie）：
Request:  {"text": "...", "schema": ["技术", "机构", "人物", "项目"]}
Response: {"result": {"技术": [{"text": "...", "start": 0, "end": 4, "probability": 0.92}], ...}}
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from metaprofile.foundation.ner.bert_crf import NERSpan
from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.utils.retry import async_retry

logger = structlog.get_logger(__name__)

# UIE schema 标签 → EntityType
_UIE_SCHEMA_MAP: dict[str, EntityType] = {
    "技术": EntityType.TECH,
    "机构": EntityType.ORG,
    "人物": EntityType.PERSON,
    "项目": EntityType.PROJECT,
}

_DEFAULT_SCHEMA = list(_UIE_SCHEMA_MAP.keys())


class UIENER:
    """
    UIE NER 推理客户端。

    schema 可按需定制，例如仅抽取技术和人物：
        ner = UIENER(schema=["技术", "人物"])
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8081",
        schema: list[str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._schema = schema or _DEFAULT_SCHEMA
        self._client = client or httpx.AsyncClient(
            timeout=settings.collectors.request_timeout
        )

    @async_retry(max_attempts=3, exceptions=(httpx.HTTPError,))
    async def predict(self, text: str) -> list[NERSpan]:
        """调用 UIE 服务，返回 NERSpan 列表（与 BertCRFNER 接口兼容）。"""
        resp = await self._client.post(
            f"{self._base_url}/uie",
            json={"text": text, "schema": self._schema},
        )
        resp.raise_for_status()
        data = resp.json()

        spans: list[NERSpan] = []
        result: dict[str, list[dict[str, Any]]] = data.get("result", {})

        for schema_label, entities in result.items():
            entity_type = _UIE_SCHEMA_MAP.get(schema_label)
            if entity_type is None:
                continue
            for ent in entities:
                spans.append(
                    NERSpan(
                        text=ent["text"],
                        label=entity_type,
                        start=int(ent.get("start", 0)),
                        end=int(ent.get("end", len(ent["text"]))),
                        confidence=float(ent.get("probability", 0.0)),
                    )
                )

        logger.debug(
            "uie_predict_done",
            text_len=len(text),
            entity_count=len(spans),
        )
        return spans

    async def predict_batch(self, texts: list[str]) -> list[list[NERSpan]]:
        results: list[list[NERSpan]] = []
        for text in texts:
            try:
                spans = await self.predict(text)
            except Exception as exc:
                logger.warning("uie_batch_item_failed", error=str(exc))
                spans = []
            results.append(spans)
        return results

    async def aclose(self) -> None:
        await self._client.aclose()
