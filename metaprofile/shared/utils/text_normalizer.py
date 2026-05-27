"""企业名称等文本标准化工具。"""
from __future__ import annotations

import re
import unicodedata

_ORG_SUFFIXES = re.compile(
    r"(股份有限公司|有限责任公司|有限公司|责任有限公司|集团有限公司|"
    r"控股有限公司|投资有限公司|科技有限公司|集团公司|研究院|研究所|"
    r"实验室|研发中心|技术中心|工程中心|大学)$"
)

_WHITESPACE = re.compile(r"\s+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_org_name(name: str | None) -> str:
    """机构/企业名称标准化：全角转半角 + 去空白。"""
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name).strip()
    return _WHITESPACE.sub("", name)


def strip_org_suffix(name: str) -> str:
    """去除机构名称常见后缀，用于消歧前的模糊匹配。"""
    return _ORG_SUFFIXES.sub("", normalize_org_name(name)).strip()


def normalize_person_name(name: str | None) -> str:
    """人名规范化：全角转半角 + 去空白。"""
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name).strip()
    return _WHITESPACE.sub("", name)


def clean_text(text: str | None) -> str:
    """通用文本清洗：去控制字符、规范空白。"""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_CHARS.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


def truncate_text(text: str, max_chars: int) -> str:
    """截断文本，保留完整 Unicode 字符（不截断代理对）。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"
