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


def _worker(table: str, seg: tuple[int, int], pk: str, col_sql: str, ph: str,
            batch: int, wm, worker_id: int, state: dict, lock) -> None:
    """单 worker 拉自己负责的 pk 区间(独立远/本地连接)。"""
    rem = pymysql.connect(**REMOTE)
    loc = pymysql.connect(**LOCAL)
    lo, hi = seg
    wcur = loc.cursor()
    try:
        cur = lo
        while cur <= hi:
            end = cur + state["pk_chunk"]
            where = (f"WHERE `{pk}` >= {cur} AND `{pk}` < {end} "
                     f"AND `update_time` > %s" if wm
                     else f"WHERE `{pk}` >= {cur} AND `{pk}` < {end}")
            params = (wm,) if wm else ()
            rcur = rem.cursor(pymysql.cursors.SSCursor)
            rcur.execute(
                f"SELECT {col_sql} FROM `{table}` {where} ORDER BY `{pk}`", params,
            )
            while True:
                rows = rcur.fetchmany(batch)
                if not rows:
                    break
                wcur.executemany(
                    f"INSERT INTO `{table}` ({col_sql}) VALUES ({ph})", rows,
                )
                loc.commit()
                with lock:
                    state["total"] += len(rows)
                    n = state["total"]
                if len(rows) >= batch and (n // batch) % 10 == 0:
                    print(f"  {table} w{worker_id}: +{n} rows "
                          f"({time.time()-state['t0']:.0f}s)", flush=True)
            rcur.close()
            cur = end
    except Exception as exc:  # noqa: BLE001
        print(f"  {table} w{worker_id} SEG[{lo},{hi}] FAILED: {exc}", flush=True)
    finally:
        rem.close()
        loc.close()


def sync_table(table: str, batch: int, pk_chunk: int = 0,
               full: bool = False, workers: int = 1) -> dict:
    import threading

    rem = pymysql.connect(**REMOTE)
    loc = pymysql.connect(**LOCAL)
    try:
        cols = cols_of(rem, table)
        # 主键列:company 表无 id(用 company_id),其余按 id
        pk = "company_id" if "company_id" in cols else ("id" if "id" in cols else cols[0])
        col_sql = ", ".join(f"`{c}`" for c in cols)
        ph = ", ".join(["%s"] * len(cols))
        lcur = loc.cursor()
        lcur.execute(f"SELECT MAX(`update_time`) FROM `{table}`")
        wm = lcur.fetchone()[0]
        lcur.close()
        if full:
            wm = None   # 全量重拉(Doris UNIQUE 按 pk 幂等,重复行内更新)

        state = {"total": 0, "t0": time.time(), "pk_chunk": pk_chunk}
        lock = threading.Lock()

        if pk_chunk > 0 and workers > 1:
            # 并行:pk 总区间切 workers 段,各线程独立连接拉(单 TCP 受
            # RTT 窗口限,多连接近线性,直到物理带宽顶)
            rcur0 = rem.cursor()
            rcur0.execute(f"SELECT MIN(`{pk}`), MAX(`{pk}`) FROM `{table}`")
            lo, hi = rcur0.fetchone()
            rcur0.close()
            lo_i, hi_i = int(lo or 0), int(hi or 0)
            span = (hi_i - lo_i + workers) // workers
            threads = []
            for w in range(workers):
                seg = (lo_i + w * span, min(lo_i + (w + 1) * span - 1, hi_i))
                t = threading.Thread(
                    target=_worker,
                    args=(table, seg, pk, col_sql, ph, batch, wm, w, state, lock),
                    daemon=True,
                )
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        else:
            wcur = loc.cursor()

            def _drain(rcur) -> None:
                while True:
                    rows = rcur.fetchmany(batch)
                    if not rows:
                        break
                    wcur.executemany(
                        f"INSERT INTO `{table}` ({col_sql}) VALUES ({ph})", rows,
                    )
                    loc.commit()
                    state["total"] += len(rows)
                    print(f"  {table}: +{state['total']} rows "
                          f"({time.time()-state['t0']:.0f}s)", flush=True)
                rcur.close()

            if pk_chunk > 0:
                rcur0 = rem.cursor()
                rcur0.execute(f"SELECT MIN(`{pk}`), MAX(`{pk}`) FROM `{table}`")
                lo, hi = rcur0.fetchone()
                rcur0.close()
                cur = int(lo or 0)
                hi_i = int(hi or 0)
                while cur <= hi_i:
                    end = cur + pk_chunk
                    where = (f"WHERE `{pk}` >= {cur} AND `{pk}` < {end} "
                             f"AND `update_time` > %s" if wm
                             else f"WHERE `{pk}` >= {cur} AND `{pk}` < {end}")
                    params = (wm,) if wm else ()
                    rcur = rem.cursor(pymysql.cursors.SSCursor)
                    rcur.execute(
                        f"SELECT {col_sql} FROM `{table}` {where} "
                        f"ORDER BY `{pk}`", params,
                    )
                    _drain(rcur)
                    cur = end
            else:
                where = "WHERE `update_time` > %s" if wm else ""
                params = (wm,) if wm else ()
                rcur = rem.cursor(pymysql.cursors.SSCursor)
                rcur.execute(
                    f"SELECT {col_sql} FROM `{table}` {where} ORDER BY `{pk}`",
                    params,
                )
                _drain(rcur)
        return {"table": table, "watermark": str(wm),
                "new_rows": state["total"],
                "seconds": round(time.time() - state["t0"], 1)}
    finally:
        rem.close()
        loc.close()


def main() -> None:
    global REMOTE, LOCAL
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default=",".join(DEFAULT_TABLES))
    ap.add_argument("--batch", type=int, default=2000)
    ap.add_argument("--pk-chunk", type=int, default=0,
                    help="主键分段扫描窗口(宽表如 company 用,如 200000)")
    ap.add_argument("--full", action="store_true",
                    help="忽略 watermark 全量重拉(Doris UNIQUE 幂等)")
    ap.add_argument("--workers", type=int, default=1,
                    help="并行连接数(pk-chunk 模式下按 pk 区间分工)")
    args = ap.parse_args()
    REMOTE = _dsn(1)
    LOCAL = _dsn(2)
    for t in args.tables.split(","):
        t = t.strip()
        if not t:
            continue
        try:
            print("SYNC", t, flush=True)
            print(" ", sync_table(t, args.batch, pk_chunk=args.pk_chunk,
                                  full=args.full, workers=args.workers),
                  flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {t} FAILED: {exc}", flush=True)


if __name__ == "__main__":
    main()
