"""弱信号语料加载：从 ODS Doris 读论文/专利/市场/附件 4 源 → CorpusDoc。

复用 ingest_ods 的 resolve_dsn + DBConnectionORM 解析连接。每源失败降级空列表
（单源不可用不杀整次提取）。附件源 attachment_text 表可能不存在（附件 spec 独立
实现）→ 同样降级。

【设计决策 / 偏离 plan 之处】
1. CorpusDoc.source 携带**短源键**("science"/"patent"/"market"/"attachment")，
   不是 ODS 表名 —— 下游 build_term_stats (T7) 用它做 df_by_source 的 key，测试也
   据此断言 source=="science"。ODS 表名只用于拼 SQL（存于 _SOURCE_SPECS）。
2. load() 的前 4 个参数为 positional-or-keyword：T8 用 keyword 调用，测试用
   positional 调用，两者都要满足。session 仍为 keyword-only 默认 None。
3. get_session 在模块顶部导入（而非函数内），以便测试 patch
   `corpus_loader.get_session` 避开真实 Postgres。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date

import pymysql
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn
from metaprofile.shared.config.settings import settings
from metaprofile.shared.db.postgres import get_session

logger = structlog.get_logger(__name__)


# 源 → (ODS 表, 文本列[拼成 text], 时间列, 实体列[拆成 entities])
# 表名仅用于拼 SQL；CorpusDoc.source 始终是短源键。
_SOURCE_SPECS: dict[str, tuple[str, list[str], str, list[str]]] = {
    "science":    ("ods_science_literature",  ["title", "abstract"], "pubdate",      ["keyword"]),
    "patent": (
        "ods_invention_patent_cn", ["title"], "filing_date",
        ["applicant", "Inventor"],
    ),
    "market":     ("ods_market_analysis_cn",  ["title"],             "event_time",   ["purchaser"]),
    "attachment": ("attachment_text",         ["clean_content"],     "extracted_at", []),
}


@dataclass
class CorpusDoc:
    source: str               # 短源键("science"/"patent"/...)，非表名
    doc_id: str
    text: str
    timestamp: date
    entities: list[str] = field(default_factory=list)


def _split_entities(raw) -> list[str]:
    """keyword/applicant 等常为分隔符串（; , ｜ 等）→ 拆实体。"""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    out: list[str] = []
    raw_s = str(raw)
    for sep in ("｜", "|", ",", "，"):
        raw_s = raw_s.replace(sep, ";")
    for part in raw_s.split(";"):
        p = part.strip()
        if p:
            out.append(p)
    return out


def _fetch_source(source_name: str, dsn: dict, spec: tuple[str, list[str], str, list[str]],
                  period_from: date, period_to: date, limit: int) -> list[CorpusDoc]:
    table, text_cols, time_col, ent_cols = spec
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        col_refs = ["`id`"] + [f"`{c}`" for c in text_cols + ent_cols] + [f"`{time_col}`"]
        cols_sql = ", ".join(col_refs)
        sql = (
            f"SELECT {cols_sql} FROM `{table}` "
            f"WHERE `{time_col}` IS NOT NULL AND `{time_col}` >= %s AND `{time_col}` <= %s "
            f"ORDER BY id LIMIT %s"
        )
        cur.execute(sql, (period_from, period_to, limit))
        cols = [d[0] for d in cur.description]
        docs: list[CorpusDoc] = []
        for r in cur.fetchall():
            row = dict(zip(cols, r, strict=False))
            ts = row.get(time_col)
            if not isinstance(ts, date):
                continue
            text = " ".join(str(row.get(c, "") or "") for c in text_cols).strip()
            if not text:
                continue
            ents: list[str] = []
            for ec in ent_cols:
                ents.extend(_split_entities(row.get(ec)))
            docs.append(CorpusDoc(
                source=source_name, doc_id=str(row.get("id")),
                text=text, timestamp=ts, entities=ents,
            ))
        cur.close()
        return docs
    finally:
        conn.close()


class CorpusLoader:
    """按 db_connection_id 解析 Doris 连接 → 读指定源语料。"""

    async def load(
        self,
        db_connection_id,
        source,
        period_from,
        period_to,
        *,
        session: AsyncSession | None = None,
    ) -> list[CorpusDoc]:
        spec = _SOURCE_SPECS.get(source)
        if spec is None:
            logger.warning("corpus_unknown_source", source=source)
            return []

        async def _resolve(sess: AsyncSession) -> dict | None:
            conn_orm = await sess.get(DBConnectionORM, db_connection_id)
            if conn_orm is None:
                logger.warning("corpus_db_connection_not_found", db_connection_id=db_connection_id)
                return None
            return resolve_dsn(conn_orm)

        if session is not None:
            dsn = await _resolve(session)
        else:
            async with get_session() as sess:
                dsn = await _resolve(sess)
        if dsn is None:
            return []

        limit = settings.weak_signal.max_docs_per_source
        try:
            return await asyncio.to_thread(
                _fetch_source, source, dsn, spec, period_from, period_to, limit,
            )
        except Exception as exc:  # noqa: BLE001  单源失败降级空
            logger.warning("corpus_load_failed", source=source, error=str(exc))
            return []
