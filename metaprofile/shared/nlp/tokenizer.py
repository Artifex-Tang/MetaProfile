"""
中文分词封装（jieba）。

统一接口，便于未来切换 pkuseg / HanLP。
"""
from __future__ import annotations

import jieba
import jieba.analyse
import structlog

logger = structlog.get_logger(__name__)

_initialized = False


def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    jieba.initialize()
    _initialized = True


class ChineseTokenizer:
    """jieba 分词封装。"""

    def tokenize(self, text: str, *, cut_all: bool = False) -> list[str]:
        _ensure_initialized()
        return [t for t in jieba.cut(text, cut_all=cut_all) if t.strip()]

    def tokenize_for_search(self, text: str) -> list[str]:
        """搜索模式分词（更细粒度，适合全文检索建索引）。"""
        _ensure_initialized()
        return [t for t in jieba.cut_for_search(text) if t.strip()]

    def add_words(self, words: list[str], freq: int = 1000) -> None:
        for word in words:
            jieba.add_word(word, freq=freq)

    def load_user_dict(self, dict_path: str) -> None:
        jieba.load_userdict(dict_path)
        logger.info("jieba_user_dict_loaded", path=dict_path)


_default_tokenizer: ChineseTokenizer | None = None


def get_tokenizer() -> ChineseTokenizer:
    global _default_tokenizer
    if _default_tokenizer is None:
        _default_tokenizer = ChineseTokenizer()
    return _default_tokenizer
