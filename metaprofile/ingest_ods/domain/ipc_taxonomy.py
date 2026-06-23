"""IPC 分类回卷 + 字典查名。L1 技术域 = IPC subclass(如 G06T)。"""
from __future__ import annotations
import re
from functools import lru_cache
from pathlib import Path

_SUBCLASS_RE = re.compile(r"^([A-H]\d{2}[A-Z])")
_DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "ipc_subclass_cn.tsv"


def subclass_of(ipc_type: str | None) -> str | None:
    if not ipc_type:
        return None
    m = _SUBCLASS_RE.match(str(ipc_type).strip().upper())
    return m.group(1) if m else None


def section_of(subclass: str | None) -> str | None:
    if not subclass or len(subclass) < 1:
        return None
    s = str(subclass).strip().upper()
    return s[0] if s and s[0].isalpha() else None


@lru_cache(maxsize=1)
def _load_dict() -> dict[str, str]:
    d: dict[str, str] = {}
    if not _DICT_PATH.exists():
        return d
    for line in _DICT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 2:
            d[parts[0].strip().upper()] = parts[1].strip()
    return d


def name_of(subclass: str | None) -> str:
    if not subclass:
        return ""
    table = _load_dict()
    return table.get(str(subclass).strip().upper(), str(subclass).strip().upper())
