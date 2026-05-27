"""
原始文档去重器。

策略（按优先级）：
1. 精确去重：raw_id + source 完全相同 → 丢弃
2. 标题模糊去重：SimHash 或归一化标题相似度 ≥ 0.95 → 标记重复
   （标题 None 跳过模糊去重）
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

import structlog

from metaprofile.foundation.collectors.base import RawDocument

logger = structlog.get_logger(__name__)

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def _normalize_title(title: str) -> str:
    """标题标准化：小写 + 去标点 + 合并空白。"""
    t = unicodedata.normalize("NFKC", title.lower())
    t = _PUNCT.sub(" ", t)
    return _SPACE.sub(" ", t).strip()


def _title_fingerprint(title: str) -> str:
    """标题指纹（MD5，用于快速查重）。"""
    return hashlib.md5(_normalize_title(title).encode("utf-8")).hexdigest()


class Deduplicator:
    """
    内存内去重（适合单批次 < 10k 文档）。
    生产环境可换为 Redis Set 存储 seen keys 以跨批次去重。
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()       # source:raw_id
        self._seen_titles: set[str] = set()    # title fingerprint

    def _id_key(self, doc: RawDocument) -> str:
        return f"{doc.source}:{doc.raw_id}"

    def is_duplicate(self, doc: RawDocument) -> bool:
        id_key = self._id_key(doc)
        if id_key in self._seen_ids:
            return True
        if doc.title:
            fp = _title_fingerprint(doc.title)
            if fp in self._seen_titles:
                return True
        return False

    def mark_seen(self, doc: RawDocument) -> None:
        self._seen_ids.add(self._id_key(doc))
        if doc.title:
            self._seen_titles.add(_title_fingerprint(doc.title))

    def dedup(self, docs: list[RawDocument]) -> tuple[list[RawDocument], int]:
        """
        去重。返回 (unique_docs, dropped_count)。
        """
        unique: list[RawDocument] = []
        dropped = 0
        for doc in docs:
            if self.is_duplicate(doc):
                dropped += 1
                logger.debug("dedup_dropped", source=doc.source, raw_id=doc.raw_id)
            else:
                self.mark_seen(doc)
                unique.append(doc)
        return unique, dropped
