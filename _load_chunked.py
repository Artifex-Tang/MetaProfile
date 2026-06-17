import pymysql, time, io, threading, json, os
from pymysql.cursors import SSCursor
from concurrent.futures import ThreadPoolExecutor, as_completed

BATCH = 5000
WORKERS = 1   # 串行:大表单扫避免 Doris workgroup(normal,11GB)多查询堆内存触发 FullGC
REMOTE = dict(host='10.242.0.1', port=9030, user='gz_kt5', password='92f5IRTld93lDPKYZZ5p',
              database='ods_zbzx', charset='utf8mb4', connect_timeout=10, read_timeout=86400)
# 2026-06-18: 迁到本地 Doris(9030 root 无密码)。原 mp-mysql:3307 已废弃删除。
LOCAL = dict(host='127.0.0.1', port=9030, user='root', password='',
             database='ods_zbzx', charset='utf8mb4', connect_timeout=10)
# 首批:8 个小/中表(<4M 各,分钟级)。大表(company/market/patent/science)走 _load_chunked_big.py。
TARGETS = ['ods_talent_info_cn', 'ods_key_events_cn', 'ods_item_category',
           'ods_financial_info_cn', 'ods_oversea_company_info', 'ods_international_news',
           'ods_strategic_policy_cn', 'ods_industry_report_cn']

# 方案 B 抽样封顶(行数)。None/缺省=全量。company 云端 429M → 本地封 10M(~2.3%)。
# 其余大表由 _load_chunked_big.py 自行封顶(默认全量 20%)。
SAMPLE_CAP = {"ods_company_basic_info": 10_000_000}

LOG = io.open(r'E:\ccode\MetaProfile\_load_chunked.log', 'a', encoding='utf-8', buffering=1)
lock = threading.Lock()
def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    with lock: print(line, flush=True); LOG.write(line + "\n")

STATE = r'E:\ccode\MetaProfile\_load_state.json'
slock = threading.Lock()
state = json.load(io.open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {}
def save_state():
    with slock:
        tmp = STATE + '.tmp'; json.dump(state, io.open(tmp, 'w', encoding='utf-8'), ensure_ascii=False); os.replace(tmp, STATE)

def copy_table(tbl):
    if state.get(tbl, {}).get('done'):
        log(f"SKIP {tbl}: done"); return tbl, 0, 0, 0
    cap = SAMPLE_CAP.get(tbl)
    dst = pymysql.connect(**LOCAL)
    dc = dst.cursor(); dc.execute("SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'")
    dc.execute(f"SELECT COUNT(*) FROM `{tbl}`"); existing = dc.fetchone()[0]
    if existing > 0:
        log(f"RESUME {tbl}: {existing:,} rows already in local — Doris UNIQUE KEY(id,event_time) upsert 去重")
    # Doris 无 INSERT IGNORE。靠 UNIQUE KEY(id,event_time) merge-on-write upsert 幂等;
    # 每批 INSERT 前对该 id 区间做 DELETE,保证重跑(同窗/部分写入后崩溃)严格幂等。
    src = pymysql.connect(cursorclass=SSCursor, **REMOTE)
    cur = src.cursor()
    try: cur.execute("SET query_timeout=86400")   # 24h, 杜绝900s默认超时
    except Exception as e: log(f"  {tbl}: SET query_timeout failed {e}")
    try: cur.execute("SET exec_mem_limit = 68719476736")   # 64GB 单查询内存上限(默认2GB太小)
    except Exception as e: log(f"  {tbl}: SET exec_mem_limit failed {e}")
    cur.execute(f"SELECT * FROM `{tbl}`")          # 全表流式, 无ORDER BY=省内存不OOM
    collist = ",".join(f"`{d[0]}`" for d in cur.description)
    ins = f"INSERT INTO `{tbl}` ({collist}) VALUES ({','.join(['%s']*len(cur.description))})"
    t0 = time.time(); done = 0; bytes_ = 0; lastlog = 0
    stopped_at_cap = False
    # 幂等说明:Doris 本地表为 UNIQUE KEY(id,event_time) merge-on-write,重插同主键自动 upsert。
    #   小表整表一次性流式灌入,重跑=重新 upsert 同一行,天然幂等无需 DELETE。
    #   注意:不能按 batch 做 DELETE id BETWEEN —— 流式无序,batch 间 id 范围会重叠互删(实测丢行)。
    while True:
        rows = cur.fetchmany(BATCH)
        if not rows: break
        dc.executemany(ins, rows); dst.commit(); done += len(rows)
        for r in rows:
            for v in r:
                if isinstance(v, (bytes, str)): bytes_ += len(v)
        if bytes_ - lastlog > 1000 * 1024 * 1024:   # 每1GB报一次
            rate = bytes_/(time.time()-t0)/1024/1024
            log(f"  {tbl}: {done:,} rows {bytes_/1024/1024/1024:.1f}GB {rate:.1f}MB/s" + (f" (cap={cap:,})" if cap else ""))
            lastlog = bytes_
        if cap is not None and done >= cap:
            log(f"  {tbl}: hit SAMPLE_CAP {cap:,} (done={done:,}) — STOP table")
            stopped_at_cap = True; break
    cur.close(); src.close()
    dc.execute(f"SELECT COUNT(*) FROM `{tbl}`"); local_n = dc.fetchone()[0]
    dst.close(); dt = time.time() - t0
    state[tbl] = {'done': True, 'rows': local_n, 'capped': stopped_at_cap}; save_state()
    tag = " CAP" if stopped_at_cap else ""
    log(f"DONE{tag} {tbl}: rows={done:,} local={local_n:,} {bytes_/1024/1024/1024:.1f}GB {dt/3600:.1f}h {bytes_/max(dt,1)/1024/1024:.1f}MB/s")
    return tbl, done, bytes_, dt

def main():
    log(f"==== CHUNKED→本地Doris start: {len(TARGETS)} tables x {WORKERS}w (LOCAL=127.0.0.1:9030 UNIQUE-KEY upsert幂等 + SAMPLE_CAP) ====")
    g0 = time.time(); gr = 0; gb = 0; ok = []; fail = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(copy_table, t): t for t in TARGETS}
        for f in as_completed(futs):
            t = futs[f]
            try:
                tbl, r, b, dt = f.result(); gr += r; gb += b; ok.append(t)
            except Exception as e:
                log(f"FAIL  {t}: {type(e).__name__}: {str(e)[:200]}"); fail.append(t)
    gdt = time.time() - g0
    log(f"==== P1 DONE: ok={len(ok)} fail={len(fail)} rows={gr:,} {gb/1024/1024/1024:.1f}GB {gdt/3600:.1f}h avg={gb/gdt/1024/1024:.1f}MB/s ====")
    if fail: log(f"FAILED: {fail}")
    LOG.close()

if __name__ == '__main__':
    main()
