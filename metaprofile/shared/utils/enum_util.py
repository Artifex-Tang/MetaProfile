"""枚举防御工具。

真实 ODS 数据常含自由文本(工学博士/中标/评标/...)塞进画像模型的枚举字段。
OrmToResponse 直接 `Enum(value)` 会抛 ValueError → 详情接口 500。
safe_enum 兜底:值不在枚举返回 default(通常 None),不抛。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, TypeVar

E = TypeVar("E", bound=Enum)


def safe_enum(enum_cls: type[E], value: Any, default: E | None = None) -> E | None:
    """Enum(value) 防御。value 为 None 或不在枚举 → default,不抛。"""
    if value is None or value == "":
        return default
    try:
        return enum_cls(value)
    except (ValueError, KeyError):
        return default


def safe_enum_list(enum_cls: type[E], values: Any) -> list[E]:
    """对列表逐项 safe_enum,丢非法项(不引入 None)。values 非列表/None → []。"""
    if not values:
        return []
    out: list[E] = []
    for v in values:
        e = safe_enum(enum_cls, v)
        if e is not None:
            out.append(e)
    return out
