"""
实体合并器。

输入：消歧判定为同一实体的两条记录（merge_from → merge_to）。
操作：
1. 从 PostgreSQL 读取双方属性，字段级合并（优先非空、较新时间戳）
2. 将 Neo4j 中指向 merge_from 的所有关系重定向到 merge_to
3. 从三库删除 merge_from 记录
4. 更新 merge_to 记录
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from metaprofile.shared.schemas.base import EntityType

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    merge_to_id: str
    merge_from_id: str
    entity_type: EntityType
    merged_fields: list[str]   # 从 merge_from 补充进来的字段
    redirected_relations: int


class EntityMerger:
    """将 merge_from 实体合并入 merge_to，清理 merge_from。"""

    def __init__(self, unified_repo: Any) -> None:
        # unified_repo: UnifiedRepo（避免循环引入，用 Any）
        self._repo = unified_repo

    async def merge(
        self,
        *,
        entity_type: EntityType,
        merge_to_id: str,
        merge_from_id: str,
    ) -> MergeResult:
        to_doc = await self._repo.get_entity(entity_type, merge_to_id)
        from_doc = await self._repo.get_entity(entity_type, merge_from_id)

        if to_doc is None:
            raise ValueError(f"merge_to entity not found: {merge_to_id}")
        if from_doc is None:
            raise ValueError(f"merge_from entity not found: {merge_from_id}")

        merged_attrs, filled_fields = _merge_attributes(to_doc, from_doc)
        redirected = await self._redirect_neo4j_relations(
            entity_type, merge_from_id, merge_to_id
        )

        await self._repo.upsert_entity(entity_type, merge_to_id, merged_attrs)
        await self._repo.delete_entity(entity_type, merge_from_id)

        logger.info(
            "merged entity",
            extra={
                "merge_to": merge_to_id,
                "merge_from": merge_from_id,
                "entity_type": entity_type,
                "filled_fields": filled_fields,
                "redirected_relations": redirected,
            },
        )

        return MergeResult(
            merge_to_id=merge_to_id,
            merge_from_id=merge_from_id,
            entity_type=entity_type,
            merged_fields=filled_fields,
            redirected_relations=redirected,
        )

    async def _redirect_neo4j_relations(
        self,
        entity_type: EntityType,
        from_id: str,
        to_id: str,
    ) -> int:
        """
        将 Neo4j 中 merge_from 的所有关系重建到 merge_to。
        原关系删除由 delete_entity_node 处理（级联删除关系）。
        """
        neo4j_repo = self._repo._neo4j
        if neo4j_repo is None:
            return 0

        label = _entity_label(entity_type)
        try:
            triples = await neo4j_repo.get_entity_relations(from_id, label)
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to read neo4j relations for redirect: %s", exc)
            return 0

        count = 0
        for triple in triples:
            try:
                # Repoint subject or object to merge_to
                subj_id = to_id if triple.get("subject_id") == from_id else triple["subject_id"]
                obj_id = to_id if triple.get("object_id") == from_id else triple["object_id"]
                subj_label = triple.get("subject_label", label)
                obj_label = triple.get("object_label", label)

                await neo4j_repo._repo.upsert_relation(
                    from_label=subj_label,
                    from_id=subj_id,
                    to_label=obj_label,
                    to_id=obj_id,
                    rel_type=triple["relation"],
                    props=triple.get("props", {}),
                )
                count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to redirect relation: %s", exc)

        return count


# ─── helpers ────────────────────────────────────────────────────────────────

def _merge_attributes(
    to_attrs: dict[str, Any],
    from_attrs: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """
    字段级合并：merge_to 优先，merge_from 补充空缺字段。
    对于数值/置信度字段取较大值；对于时间戳字段取较新值。
    """
    merged = dict(to_attrs)
    filled: list[str] = []

    for key, from_val in from_attrs.items():
        if _is_empty(from_val):
            continue
        to_val = merged.get(key)
        if _is_empty(to_val):
            merged[key] = from_val
            filled.append(key)
        elif key in ("confidence", "completeness_score"):
            if isinstance(from_val, (int, float)) and isinstance(to_val, (int, float)):
                if from_val > to_val:
                    merged[key] = from_val
                    filled.append(key)
        elif key in ("updated_at", "last_seen_at"):
            # Keep the more recent timestamp
            try:
                if str(from_val) > str(to_val):
                    merged[key] = from_val
                    filled.append(key)
            except Exception:  # noqa: BLE001
                pass

    return merged, filled


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def _entity_label(entity_type: EntityType) -> str:
    return {
        EntityType.TECH: "Tech",
        EntityType.ORG: "Org",
        EntityType.PERSON: "Person",
        EntityType.PROJECT: "Project",
    }[entity_type]
