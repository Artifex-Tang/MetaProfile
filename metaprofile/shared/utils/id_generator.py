"""实体唯一 ID 生成。"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from metaprofile.shared.schemas.base import EntityType


def new_entity_id(entity_type: EntityType) -> str:
    """生成新实体 ID：类型前缀 + 时间戳 + 短 UUID。

    示例：TECH_20260427_a1b2c3d4
    """
    short = uuid4().hex[:8]
    ts = datetime.now(UTC).strftime("%Y%m%d")
    return f"{entity_type.value}_{ts}_{short}"


def stable_id_from_attrs(entity_type: EntityType, *attrs: str) -> str:
    """基于关键属性生成稳定 ID（用于幂等去重）。

    例如：基于"机构中文名+创建时间"生成稳定 ID，
    重复处理同一机构总是产生相同 ID。
    """
    key = "::".join([entity_type.value, *(a or "" for a in attrs)])
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"{entity_type.value}_S_{digest}"
