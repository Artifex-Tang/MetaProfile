"""阶段① 表→表 抽取：Doris id-keyset 读 + 字段映射 → staging dict。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pymysql
import structlog

from metaprofile.ingest_ods.domain.mappings import apply_mapping

logger = structlog.get_logger(__name__)


def _sanitize_watermark(watermark: Any) -> str | None:
    """增量 watermark(update_time 过滤)须可解析为 datetime,否则归 None。

    垃圾值("0"/"null"/malformed ISO)会让 SQL `update_time > '0'` 命中全表
    ('0'=0000-00-00),增量过滤失效变全表扫(大表卡死)。空/falsy 同归 None,
    退化为 id-keyset 全量分页(仍按 batch_size 批读,只是无增量裁剪)。
    """
    if not watermark:
        return None
    try:
        datetime.fromisoformat(str(watermark))
    except ValueError:
        return None
    return str(watermark)


# 分页 keyset 列:多数表是 id;company_basic_info 无 id 列(PK=company_id)。
# 硬编码 id 会让 company 表 Unknown column 'id' → 整采集崩。
KEY_COL = {"ods_company_basic_info": "company_id"}


def _fetch_rows(dsn: dict, table: str, last_id: int, batch_size: int,
                watermark: str | None = None) -> list[dict]:
    """同步流式取一批行。keyset(KEY_COL 决定列),可选 update_time 增量过滤。"""
    key = KEY_COL.get(table, "id")
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        sql = f"SELECT * FROM `{table}` WHERE `{key}` > %s"
        params: list[Any] = [last_id]
        if watermark:
            sql += " AND update_time > %s"
            params.append(watermark)
        sql += f" ORDER BY `{key}` LIMIT %s"
        params.append(batch_size)
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        return rows
    finally:
        conn.close()


class Extractor:
    async def extract_batch(
        self,
        dsn: dict,
        table: str,
        last_id: int,
        batch_size: int,
        watermark: str | None = None,
    ) -> list[dict]:
        watermark = _sanitize_watermark(watermark)
        rows = await asyncio.to_thread(_fetch_rows, dsn, table, last_id, batch_size, watermark)
        now = datetime.now(timezone.utc)
        out: list[dict] = []
        max_id = last_id
        key = KEY_COL.get(table, "id")
        for row in rows:
            mapped = apply_mapping(table, row)
            if mapped is None:
                continue
            rid = row.get(key)
            if rid is not None and rid > max_id:
                max_id = rid
            out.append({
                "profile_type": mapped["profile_type"],
                "source_table": table,
                "source_id": str(rid),
                "entity_key": mapped["entity_key"],
                "raw_payload": {**row, "_attrs": mapped["attrs"]},
                "extracted_at": now,
            })
        if out:
            for o in out:
                o["last_id"] = max_id
        return out
