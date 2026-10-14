"""ODS 增量同步:云端 Doris(db_connections id=1)→ 本地 Doris(id=2)。

watermark = 本地各表 MAX(update_time)(无状态文件,幂等重跑)。
拉 remote 中 update_time > watermark 的行,分批 executemany INSERT。
凭证从 Postgres db_connections 解析(resolve_dsn)。

用法(容器内):python scripts/incremental_sync.py [--tables t1,t2] [--batch 2000]
"""
from __future__ import annotations

import argparse
import sys
import time

import pymysql

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _dsn(conn_id: int) -> dict:
    """从 db_connections 解析 DSN(容器内跑,复用既有加解密)。

    必须走 run_async(持久 loop)——asyncio.run 每次新 loop 会撞
    asyncpg 模块级 engine 的旧 loop(gotcha 见 [[tech-concept-p1-done]])。
    """
    from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
    from metaprofile.ingest_ods.services.connections import resolve_dsn
    from metaprofile.shared.db.postgres import get_session
    from metaprofile.shared.worker.async_runner import run_async

    async def _get():
        async with get_session() as s:
            orm = await s.get(DBConnectionORM, conn_id)
            return resolve_dsn(orm)
    dsn = run_async(_get())
    dsn.update(read_timeout=600, write_timeout=600)
    return dsn

DEFAULT_TABLES = [
    "ods_invention_patent_cn", "ods_science_literature",
    "ods_market_analysis_cn", "ods_company_basic_info",
    "ods_strategic_policy_cn", "ods_key_events_cn",
    "ods_industry_report_cn", "ods_international_news",
]

REMOTE: dict = {}
LOCAL: dict = {}


def cols_of(conn, table: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    out = [r[0] for r in cur.fetchall()]
    cur.close()
    return out


def sync_table(table: str, batch: int) -> dict:
    rem = pymysql.connect(**REMOTE)
    loc = pymysql.connect(**LOCAL)
    try:
        cols = cols_of(rem, table)
        col_sql = ", ".join(f"`{c}`" for c in cols)
        ph = ", ".join(["%s"] * len(cols))
        lcur = loc.cursor()
        lcur.execute(f"SELECT MAX(`update_time`) FROM `{table}`")
        wm = lcur.fetchone()[0]
        lcur.close()
        where = "WHERE `update_time` > %s" if wm else ""
        params = (wm,) if wm else ()
        rcur = rem.cursor(pymysql.cursors.SSCursor)
        rcur.execute(
            f"SELECT {col_sql} FROM `{table}` {where} "
            f"ORDER BY `update_time`, `id`", params,
        )
        wcur = loc.cursor()
        total = 0
        t0 = time.time()
        while True:
            rows = rcur.fetchmany(batch)
            if not rows:
                break
            wcur.executemany(
                f"INSERT INTO `{table}` ({col_sql}) VALUES ({ph})", rows,
            )
            loc.commit()
            total += len(rows)
            print(f"  {table}: +{total} rows ({time.time()-t0:.0f}s)", flush=True)
        rcur.close()
        wcur.close()
        return {"table": table, "watermark": str(wm), "new_rows": total,
                "seconds": round(time.time() - t0, 1)}
    finally:
        rem.close()
        loc.close()


def main() -> None:
    global REMOTE, LOCAL
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default=",".join(DEFAULT_TABLES))
    ap.add_argument("--batch", type=int, default=2000)
    args = ap.parse_args()
    REMOTE = _dsn(1)
    LOCAL = _dsn(2)
    for t in args.tables.split(","):
        t = t.strip()
        if not t:
            continue
        try:
            print("SYNC", t, flush=True)
            print(" ", sync_table(t, args.batch), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {t} FAILED: {exc}", flush=True)


if __name__ == "__main__":
    main()
