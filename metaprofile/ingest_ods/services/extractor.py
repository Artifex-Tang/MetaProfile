"""阶段① 表→表 抽取：Doris id-keyset 读 + 字段映射 → staging dict。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pymysql
import structlog

from metaprofile.ingest_ods.domain.mappings import apply_mapping

logger = structlog.get_logger(__name__)


def _fetch_rows(dsn: dict, table: str, last_id: int, batch_size: int,
                watermark: str | None = None) -> list[dict]:
    """同步流式取一批行。id-keyset，可选 update_time 增量过滤。"""
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        sql = f"SELECT * FROM `{table}` WHERE id > %s"
        params: list[Any] = [last_id]
        if watermark:
            sql += " AND update_time > %s"
            params.append(watermark)
        sql += " ORDER BY id LIMIT %s"
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
        rows = await asyncio.to_thread(_fetch_rows, dsn, table, last_id, batch_size, watermark)
        now = datetime.now(timezone.utc)
        out: list[dict] = []
        max_id = last_id
        for row in rows:
            mapped = apply_mapping(table, row)
            if mapped is None:
                continue
            rid = row.get("id")
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
