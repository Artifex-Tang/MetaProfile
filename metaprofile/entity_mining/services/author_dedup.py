"""作者消歧建议(Phase D2,规则版):blocking + 共作者 Jaccard 聚类。

数据:science authors 串(Doris)→ (作者, 共作者集, 年份集) 记录;
块内对打分 = 0.6·coauthor_jaccard + 0.3·name_similarity + 0.1·年份窗重叠
≥ 阈值(默认 0.7)写合并建议(entity_resolution_suggestion, 不自动并)。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.entity_mining.domain.orm_models import (
    EntityResolutionSuggestionORM,
)
from metaprofile.entity_mining.services.name_utils import (
    author_block_key,
    coauthor_jaccard,
    similarity,
)
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class AuthorRecord:
    name: str
    coauthors: set[str] = field(default_factory=set)
    years: set[int] = field(default_factory=set)
    source_doc_ids: set[str] = field(default_factory=set)


def parse_authors_row(authors: str | None) -> list[str]:
    """authors 串(逗号/分号/顿号分隔)→ 有序作者列表。

    过滤脏数据:超长片段(整段 JSON/地址串)、含引号+冒号的伪名。
    """
    if not authors:
        return []
    import re
    parts = re.split(r"[;；,，、]", str(authors))
    out = []
    for p in parts:
        s = p.strip()
        if len(s) < 2 or len(s) > 64:
            continue
        if '"' in s or "{" in s or ":" in s:
            continue
        out.append(s)
    return out


def build_author_records(rows: list[tuple[str, str, int]]) -> dict[str, AuthorRecord]:
    """(authors 串, doc_id, year) 行 → 作者名 → 记录(聚合共作者/年份)。"""
    records: dict[str, AuthorRecord] = {}
    for authors, doc_id, year in rows:
        names = parse_authors_row(authors)
        for i, name in enumerate(names):
            rec = records.setdefault(name, AuthorRecord(name=name))
            rec.coauthors.update(n for j, n in enumerate(names) if j != i)
            rec.years.add(int(year))
            rec.source_doc_ids.add(str(doc_id))
    return records


def dedup_pairs(records: dict[str, AuthorRecord],
                *, threshold: float = 0.7) -> list[tuple[str, str, float, float, float]]:
    """块内两两打分 → (a, b, score, jaccard, name_sim) 列表(score≥threshold)。"""
    blocks: dict[str, list[str]] = {}
    for name in records:
        key = author_block_key(name)
        if key:
            blocks.setdefault(key, []).append(name)
    out: list[tuple[str, str, float, float, float]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for names in blocks.values():
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                pair = (min(a, b), max(a, b))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                ra, rb = records[a], records[b]
                jac = coauthor_jaccard(ra.coauthors, rb.coauthors)
                nsim = similarity(a, b)
                years_overlap = 1.0 if ra.years & rb.years else 0.0
                score = 0.6 * jac + 0.3 * nsim + 0.1 * years_overlap
                if score >= threshold:
                    out.append((pair[0], pair[1], round(score, 4), round(jac, 4), round(nsim, 4)))
    return out


async def load_author_rows(db_connection_id: int | None, limit: int) -> list[tuple[str, str, int]]:
    import pymysql

    from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
    from metaprofile.ingest_ods.services.connections import resolve_dsn
    from metaprofile.shared.db.postgres import get_session

    async with get_session() as s:
        conn_orm = await s.get(DBConnectionORM, db_connection_id)
        if conn_orm is None:
            return []
        dsn = resolve_dsn(conn_orm)

    def _q() -> list[tuple[str, str, int]]:
        conn = pymysql.connect(**dsn)
        try:
            cur = conn.cursor(pymysql.cursors.SSCursor)
            cur.execute(
                "SELECT authors, id, YEAR(event_time) FROM ods_science_literature "
                "WHERE authors IS NOT NULL AND authors != '' "
                "ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = [(str(a), str(i), int(y)) for a, i, y in cur.fetchall() if y]
            cur.close()
            return rows
        finally:
            conn.close()

    return await asyncio.to_thread(_q)


async def suggest_author_merges(session: AsyncSession, *,
                                db_connection_id: int | None = None,
                                rows: list[tuple[str, str, int]] | None = None,
                                threshold: float = 0.7) -> dict:
    """端到端:拉 authors → 聚合 → 块内对 → 写合并建议。"""
    did = db_connection_id or settings.weak_signal.corpus_db_connection_id
    if rows is None:
        rows = await load_author_rows(did, limit=20000)
    records = build_author_records(rows)
    pairs = dedup_pairs(records, threshold=threshold)
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    for a, b, score, jac, nsim in pairs[:2000]:
        stmt = pg_insert(EntityResolutionSuggestionORM).values(
            entity_type="person", raw_name=a, suggestion_kind="author_dedup",
            matched_id=None, matched_name=b, score=score,
            detail={"jaccard": jac, "name_similarity": nsim,
                    "docs_a": len(records[a].source_doc_ids),
                    "docs_b": len(records[b].source_doc_ids)},
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ers_entity_kind_name",
            set_={"score": stmt.excluded.score, "detail": stmt.excluded.detail},
        )
        await session.execute(stmt)
    logger.info("author_dedup_suggested", pairs=len(pairs), authors=len(records))
    return {"status": "done", "authors": len(records), "suggestions": min(len(pairs), 2000)}
