"""证据链构建(Phase A4/A5)+ term_stats 持久化(Phase A3)。

纯函数部分(可测):
- select_evidence:doc_ids 取最近 cap 篇作证据
- cooccurrence_pairs:同文档共现的信号词对 → (a,b) 升序对 → 共现权重
- build_term_stat_rows:TermStats → term_stats 表行(仅当前期窗口)

IO 部分persist_term_stats。
"""
from __future__ import annotations

import sqlalchemy as sa
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import TermStatORM
from metaprofile.new_tech_discovery.services.signal_metrics import TermStats, Window

logger = structlog.get_logger(__name__)

_BATCH = 1000


def select_evidence(doc_ids: list[str], *, cap: int) -> list[str]:
    """doc_ids 由 build_term_stats 保证**时间戳降序（最近在前）**,取前 cap 篇。

    (审查 H2:不得按加载序取尾——加载序是源优先,非时间序。)
    """
    if cap <= 0:
        return []
    return list(doc_ids[:cap])


def cooccurrence_pairs(docs_terms: list[set[str]],
                       signal_terms: set[str]) -> dict[tuple[str, str], int]:
    """同文档共现的信号词对 → 权重(共文档数)。对内 (a,b) 按字母序,去自环。"""
    weights: dict[tuple[str, str], int] = {}
    for terms in docs_terms:
        hits = sorted(terms & signal_terms)
        for i in range(len(hits)):
            for j in range(i + 1, len(hits)):
                pair = (hits[i], hits[j])
                weights[pair] = weights.get(pair, 0) + 1
    return weights


def build_term_stat_rows(stats: list[TermStats], windows: list[Window]) -> list[dict]:
    """TermStats → term_stats 行。仅当前期窗口(历史不入库,按需可扩)。"""
    rows: list[dict] = []
    for ts in stats:
        for i, w in enumerate(windows):
            if w.is_history:
                continue
            df = ts.df_by_window[i]
            if df <= 0:
                continue
            tf = ts.tf_by_window[i] if ts.tf_by_window else df
            rows.append({
                "window_month": w.start,
                "source": "*",   # 全源合并行
                "term": ts.term,
                "term_kind": "entity" if ts.is_entity else "term",
                "df": int(df),
                "tf": int(tf),
            })
    return rows


async def persist_term_stats(session: AsyncSession, rows: list[dict]) -> int:
    """批量 upsert(ON CONFLICT (window_month,source,term,term_kind) DO UPDATE)。"""
    written = 0
    for start in range(0, len(rows), _BATCH):
        chunk = rows[start:start + _BATCH]
        stmt = pg_insert(TermStatORM).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_term_stats",
            set_={
                "df": stmt.excluded.df, "tf": stmt.excluded.tf,
                "updated_at": sa.func.now(),
            },
        )
        await session.execute(stmt)
        written += len(chunk)
    if written:
        logger.info("term_stats_persisted", rows=written)
    return written
