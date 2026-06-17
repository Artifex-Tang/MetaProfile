"""批内 (entity_type, normalized_name) → entity_id 索引。

GAP2: 关系端点解析 —— 命中→用 profile PK(对齐 Neo4j profile 节点);
未命中→保留 name: 卫星 id。这样结构化/内容挖掘产出的关系端点能与
ingest 创建的 profile 节点(entity_id=PK)连成同一张图,而非碎片化。
"""
from __future__ import annotations

from metaprofile.shared.schemas.base import EntityType


def _norm_name(attrs: dict) -> str | None:
    """从 entity attrs 取规范名:优先 name_cn,fallback tech_name_cn。

    name_cn/tech_name_cn 可能是 list(project 的 _one transform 产出),取首元素。
    """
    for k in ("name_cn", "tech_name_cn"):
        v = attrs.get(k)
        if isinstance(v, list):
            v = v[0] if v else None
        if v:
            return str(v).strip()
    return None


class NameIndex:
    """批内 (entity_type, name) → entity_id 映射。"""

    def __init__(self) -> None:
        self._m: dict[tuple[str, str], str] = {}

    def add(self, entity_type: EntityType, entity_id: str, attrs: dict) -> None:
        nm = _norm_name(attrs)
        if nm:
            self._m[(entity_type.value, nm)] = entity_id

    def resolve(self, entity_type: EntityType, name: str) -> str:
        """返回 PK id(命中)或 f"name:{name}"(未命中,卫星实体)。"""
        pk = self._m.get((entity_type.value, str(name).strip()))
        return pk if pk else f"name:{name}"
