"""
BERT-CRF NER 推理客户端。

通过 HTTP 调用本地/集群部署的 BERT-CRF 推理服务（如 Triton / TorchServe）。
输出：文本中识别到的实体 span 列表。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.utils.retry import async_retry

logger = structlog.get_logger(__name__)


@dataclass
class NERSpan:
    text: str
    label: EntityType
    start: int
    end: int
    confidence: float


_LABEL_MAP: dict[str, EntityType] = {
    "TECH": EntityType.TECH,
    "ORG": EntityType.ORG,
    "PERSON": EntityType.PERSON,
    "PROJECT": EntityType.PROJECT,
    # 兼容 BIO 标签前缀
    "B-TECH": EntityType.TECH,
    "B-ORG": EntityType.ORG,
    "B-PERSON": EntityType.PERSON,
    "B-PROJECT": EntityType.PROJECT,
}


class BertCRFNER:
    """
    BERT-CRF NER 推理服务客户端。

    推理服务接口约定（POST /predict）：
    Request:  {"text": "..."}
    Response: {"entities": [{"text": "...", "label": "TECH", "start": 0, "end": 4, "score": 0.95}]}
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            timeout=settings.collectors.request_timeout
        )

    @async_retry(max_attempts=3, exceptions=(httpx.HTTPError,))
    async def predict(self, text: str) -> list[NERSpan]:
        """调用 BERT-CRF 推理服务，返回实体 span 列表。"""
        resp = await self._client.post(
            f"{self._base_url}/predict",
            json={"text": text},
        )
        resp.raise_for_status()
        data = resp.json()

        spans: list[NERSpan] = []
        for ent in data.get("entities", []):
            label_str = ent.get("label", "")
            entity_type = _LABEL_MAP.get(label_str)
            if entity_type is None:
                logger.debug("bert_crf_unknown_label", label=label_str)
                continue
            spans.append(
                NERSpan(
                    text=ent["text"],
                    label=entity_type,
                    start=int(ent.get("start", 0)),
                    end=int(ent.get("end", 0)),
                    confidence=float(ent.get("score", 0.0)),
                )
            )

        logger.debug(
            "bert_crf_predict_done",
            text_len=len(text),
            entity_count=len(spans),
        )
        return spans

    async def predict_batch(self, texts: list[str]) -> list[list[NERSpan]]:
        """批量推理（顺序调用，避免服务端 OOM）。"""
        results: list[list[NERSpan]] = []
        for text in texts:
            try:
                spans = await self.predict(text)
            except Exception as exc:
                logger.warning("bert_crf_batch_item_failed", error=str(exc))
                spans = []
            results.append(spans)
        return results

    async def aclose(self) -> None:
        await self._client.aclose()
