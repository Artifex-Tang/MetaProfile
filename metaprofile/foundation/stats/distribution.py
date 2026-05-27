"""
字段值分布统计。

输入：实体 dict 列表（来自 PostgresRepo.list_by_type）
输出：指定字段的值频率分布（top-K）
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass
class DistributionEntry:
    value: str
    count: int
    ratio: float    # count / total


@dataclass
class FieldDistribution:
    field_name: str
    total_entities: int
    covered: int            # entities where field is present
    coverage_rate: float    # covered / total_entities
    top_values: list[DistributionEntry]


def compute_distribution(
    entities: list[dict[str, Any]],
    field_name: str,
    *,
    top_k: int = 20,
) -> FieldDistribution:
    """
    计算单字段值分布。

    支持标量字段（str/int）和列表字段（取每个元素）。

    Args:
        entities: 实体属性 dict 列表
        field_name: 字段名
        top_k: 返回最高频的 K 个值

    Returns:
        FieldDistribution
    """
    counter: Counter[str] = Counter()
    covered = 0
    total = len(entities)

    for ent in entities:
        val = ent.get(field_name)
        if val is None or val == "" or val == []:
            continue
        covered += 1
        if isinstance(val, list):
            for item in val:
                if item is not None and str(item).strip():
                    counter[str(item).strip()] += 1
        else:
            counter[str(val).strip()] += 1

    top = counter.most_common(top_k)
    total_occurrences = sum(counter.values()) or 1

    entries = [
        DistributionEntry(
            value=v,
            count=c,
            ratio=round(c / total_occurrences, 4),
        )
        for v, c in top
    ]

    return FieldDistribution(
        field_name=field_name,
        total_entities=total,
        covered=covered,
        coverage_rate=round(covered / total, 4) if total > 0 else 0.0,
        top_values=entries,
    )


def compute_multi_distribution(
    entities: list[dict[str, Any]],
    field_names: list[str],
    *,
    top_k: int = 20,
) -> dict[str, FieldDistribution]:
    """计算多字段分布，返回 {field_name: FieldDistribution}。"""
    return {f: compute_distribution(entities, f, top_k=top_k) for f in field_names}
