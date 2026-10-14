"""弱信号语料加载:从 ODS Doris 读 8 源 → CorpusDoc。

复用 ingest_ods 的 resolve_dsn + DBConnectionORM 解析连接。每源失败降级空列表
（单源不可用不杀整次提取）。附件源 attachment_text 表可能不存在（附件 spec 独立
实现）→ SHOW TABLES 探测后优雅跳过（G3，不再每次报 error）。

【2026-10-14 Phase A 修复/扩展（spec 2026-10-14 §4.1/§6-A1/A2）】
1. G1:science 时间列 pubdate → event_time（pubdate 不在 Doris DDL，查询必失败）。
2. G2:patent 实体列去掉 DDL 外的 Inventor（inventor 在 features JSON，SQL 层取不到）。
3. G3:optional 源（attachment）先探测表存在，不存在 warning 一次即跳过。
4. G9:新增 4 源 policy/key_events/industry_report/intl_news（均 title+event_time+industry）。
5. 新增 industry 域过滤参数（extract 的 domain → ODS industry 列过滤）。

设计决策（沿用）:
- CorpusDoc.source 携带短源键,ODS 表名只用于拼 SQL（存于 _SOURCE_SPECS）。
- get_session 模块顶导入以便测试 patch。
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


@dataclass(frozen=True)
class SourceSpec:
    """语料源规格:表 / 文本列 / 时间列 / 实体列。列名必须存在于 Doris DDL。"""

    table: str
    text_cols: tuple[str, ...]
    time_col: str
    ent_cols: tuple[str, ...]
    optional: bool = False   # 表可能未建（attachment_text）→ 探测后跳过


# 8 源:学术(science)+专利(patent)+市场(market)+政策(policy)+事件(key_events)
# + 行业报告(industry_report)+国际新闻(intl_news)+附件(attachment,可选)。
_SOURCE_SPECS: dict[str, SourceSpec] = {
    "science": SourceSpec(
        "ods_science_literature", ("title", "abstract"), "event_time", ("keyword",),
    ),
    "patent": SourceSpec(
        "ods_invention_patent_cn", ("title",), "filing_date", ("applicant",),
    ),
    "market": SourceSpec(
        "ods_market_analysis_cn", ("title",), "event_time", ("purchaser",),
    ),
    "policy": SourceSpec(
        "ods_strategic_policy_cn", ("title",), "event_time", ("policy_source",),
    ),
    "key_events": SourceSpec(
        "ods_key_events_cn", ("title",), "event_time", (),
    ),
    "industry_report": SourceSpec(
        "ods_industry_report_cn", ("title",), "event_time", ("publishing_organization",),
    ),
    "intl_news": SourceSpec(
        "ods_international_news", ("title",), "event_time", (),
    ),
    "attachment": SourceSpec(
        "attachment_text", ("clean_content",), "extracted_at", (), optional=True,
    ),
}

# optional 源集合（表未建则跳过,不比对 DDL）
_OPTIONAL_SOURCES = {
    name for name, spec in _SOURCE_SPECS.items() if spec.optional
}

# 已探测不存在的 optional 表,按 (db_connection_id, table) 缓存
# (多连接下 A 连接缺表不应永久遮蔽 B 连接;进程内不设 TTL,重启刷新)
_MISSING_TABLES: set[tuple[int | None, str]] = set()


@dataclass
class CorpusDoc:
    source: str               # 短源键("science"/"patent"/...),非表名
    doc_id: str
    text: str
    timestamp: date
    entities: list[str] = field(default_factory=list)


def _split_entities(raw) -> list[str]:
    """keyword/applicant 等常为分隔符串(; , ｜ 等)→ 拆实体。"""
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


def _table_exists(conn, db_connection_id: int | None, table: str) -> bool:
    """SHOW TABLES 精确匹配探测(optional 源用);不存在记入缓存返回 False。

    全量 SHOW TABLES + 集合成员判断(LIKE 的 `_` 是单字符通配,会误命中)。
    """
    key = (db_connection_id, table)
    if key in _MISSING_TABLES:
        return False
    cur = conn.cursor()
    try:
        cur.execute("SHOW TABLES")
        found = table in {r[0] for r in cur.fetchall()}
        if not found:
            _MISSING_TABLES.add(key)
            logger.info("corpus_optional_table_missing", table=table)
        return found
    finally:
        cur.close()


def _fetch_source(source_name: str, dsn: dict, spec: SourceSpec,
                  period_from: date, period_to: date, limit: int,
                  industry: str | None = None,
                  db_connection_id: int | None = None) -> list[CorpusDoc]:
    table, text_cols, time_col, ent_cols = (
        spec.table, spec.text_cols, spec.time_col, spec.ent_cols,
    )
    conn = pymysql.connect(**dsn)
    try:
        if spec.optional and not _table_exists(conn, db_connection_id, table):
            return []
        cur = conn.cursor(pymysql.cursors.SSCursor)
        col_refs = ["`id`"] + [f"`{c}`" for c in text_cols + ent_cols] + [f"`{time_col}`"]
        cols_sql = ", ".join(col_refs)
        where = (
            f"`{time_col}` IS NOT NULL AND `{time_col}` >= %s AND `{time_col}` <= %s"
        )
        params: list = [period_from, period_to]
        if industry:
            where += " AND `industry` = %s"
            params.append(industry)
        sql = f"SELECT {cols_sql} FROM `{table}` WHERE {where} ORDER BY id LIMIT %s"
        params.append(limit)
        cur.execute(sql, tuple(params))
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
            # doc_id 带源前缀:各 ODS 表 id 序列独立,裸 id 跨源必然碰撞
            # (审查 H1:evidence_doc_ids 须可定位回源表)
            docs.append(CorpusDoc(
                source=source_name, doc_id=f"{source_name}:{row.get('id')}",
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
        industry: str | None = None,
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
                industry, db_connection_id,
            )
        except Exception as exc:  # noqa: BLE001  单源失败降级空
            logger.warning("corpus_load_failed", source=source, error=str(exc))
            return []
