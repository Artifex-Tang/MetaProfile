import pymysql, time, io, threading, json, os
from pymysql.cursors import SSCursor

# 大表分块灌:绕 Doris workgroup(normal,11GB)内存墙。market/patent 全表扫单查询吃31GB必OOM。
# 策略:按 id 区间分窗,每窗<=WINDOW_ROWS行(控单查询内存<11GB),COUNT二分定窗上界;
#       每窗 DELETE[id,hi)+INSERT 幂等(本地 Doris 无 IGNORE),每窗存last=真续传不重读。
# 2026-06-17 抗silent-stall:VPN/代理路径~30min静默断流(read_timeout=86400→pymysql傻等24h)。
#   解:①每窗全新rc+wf连接(不带stalled socket);②read_timeout=600(stall 10min内报错);
#       ③每窗fetch重试3次(INSERT IGNORE幂等,重连重取自愈);④WINDOW_ROWS=500K(每窗~15min<<30min阈值)。
BATCH = 5000
WINDOW_ROWS = 500_000          # 每窗行数上限;~15min/窗 @0.9MB/s,远低于~30min stall阈值
BISECT_MAX_ITERS = 35
READ_TIMEOUT = 600             # 单次socket读最长秒数;stall(无数据)>此值即报错,触发重试
FETCH_RETRIES = 3              # 每窗fetch重试次数
REMOTE = dict(host='10.242.0.1', port=9030, user='gz_kt5', password='92f5IRTld93lDPKYZZ5p',
              database='ods_zbzx', charset='utf8mb4', connect_timeout=10, read_timeout=86400)
# 2026-06-18: 迁到本地 Doris(9030 root 无密码)。原 mp-mysql:3307 已废弃删除。
LOCAL = dict(host='127.0.0.1', port=9030, user='root', password='',
             database='ods_zbzx', charset='utf8mb4', connect_timeout=10)
# 首批只跑 science(6.85M,最小大表,作大表首测)。market/patent/company 后续再放开。
BIG = ['ods_science_literature']

LOG = io.open(r'E:\ccode\MetaProfile\_load_big.log', 'a', encoding='utf-8', buffering=1)
lock = threading.Lock()
def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    with lock: print(line, flush=True); LOG.write(line + "\n")

STATE = r'E:\ccode\MetaProfile\_load_big_state.json'
slock = threading.Lock()
state = json.load(io.open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {}
def save_state():
    with slock:
        tmp = STATE + '.tmp'; json.dump(state, io.open(tmp, 'w', encoding='utf-8'), ensure_ascii=False); os.replace(tmp, STATE)

def conn_remote(stream=False, read_timeout=READ_TIMEOUT):
    kw = dict(REMOTE); kw['read_timeout'] = read_timeout
    if stream: kw['cursorclass'] = SSCursor
    c = pymysql.connect(**kw)
    cur = c.cursor()
    try: cur.execute("SET query_timeout=86400")        # Doris侧:杜绝对长扫描的900s默认cancel
    except Exception as e: log(f"  SET query_timeout fail {e}")
    try: cur.execute("SET exec_mem_limit = 68719476736")
    except Exception as e: log(f"  SET exec_mem_limit fail {e}")
    return c, cur

def bisect_end(rcur, tbl, lo, max_id, target):
    a, b = lo + 1, max_id + 1; best = lo + 1
    for _ in range(BISECT_MAX_ITERS):
        if b - a <= 1: break
        mid = (a + b) // 2
        rcur.execute(f"SELECT COUNT(*) FROM `{tbl}` WHERE `id`>={lo} AND `id`<{mid}")
        c = rcur.fetchone()[0]
        if c <= target: best = mid; a = mid
        else: b = mid
    return best

def load_chunked(tbl):
    if state.get(tbl, {}).get('done'):
        log(f"SKIP {tbl}: done"); return
    rc, rcur = conn_remote()
    rcur.execute(f"SELECT MIN(`id`), MAX(`id`) FROM `{tbl}`")
    min_id, max_id = rcur.fetchone(); rc.close()
    if min_id is None:
        log(f"SKIP {tbl}: empty on remote"); return
    lo = state.get(tbl, {}).get('last', min_id)
    dst = pymysql.connect(**LOCAL); dc = dst.cursor(); dc.execute("SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'")
    dc.execute(f"SELECT COUNT(*) FROM `{tbl}`"); have = dc.fetchone()[0]
    log(f"START {tbl}: id[{min_id},{max_id}] resume_from={lo} local已有{have:,}行")
    collist = ins = None; wno = 0; t0 = time.time(); gbytes = 0; ggot = 0
    while lo <= max_id:
        # 每窗全新 rc 做 bisect(防复用 stalled 连接)
        rc, rcur = conn_remote()
        try:
            end = bisect_end(rcur, tbl, lo, max_id, WINDOW_ROWS)
            rcur.execute(f"SELECT COUNT(*) FROM `{tbl}` WHERE `id`>={lo} AND `id`<{end}")
            c = rcur.fetchone()[0]
            if end <= lo or c == 0:
                rcur.execute(f"SELECT MIN(`id`) FROM `{tbl}` WHERE `id`>={lo}")
                nid = rcur.fetchone()[0]
                if nid is None:
                    log(f"  {tbl}: no rows>= {lo}"); rc.close(); break
                end = nid + 1
        finally:
            rc.close()
        # 每窗全新 wf 流式取数 + 重试(stall自愈);DELETE+INSERT 幂等,重连重取不重复
        got = 0; wb = 0; ok = False
        for attempt in range(1, FETCH_RETRIES + 1):
            wf = wcur = None
            try:
                wf, wcur = conn_remote(stream=True)
                wcur.execute(f"SELECT * FROM `{tbl}` WHERE `id`>={lo} AND `id`<{end}")
                if collist is None:
                    collist = ",".join(f"`{d[0]}`" for d in wcur.description)
                    ins = f"INSERT INTO `{tbl}` ({collist}) VALUES ({','.join(['%s']*len(wcur.description))})"
                # Doris 无 INSERT IGNORE → 窗口幂等:取数前 DELETE 整个 id 窗 [lo,end),
                #   再整窗 INSERT。重跑同窗(崩溃/重试)重新 DELETE+INSERT,严格无重复。
                #   注:本地 Doris 表为 UNIQUE KEY(id,event_time) MoW,upsert 本就幂等;
                #       DELETE 仅作显式保险(覆盖任何 schema 边界)。
                dc.execute(f"DELETE FROM `{tbl}` WHERE `id` >= %s AND `id` < %s", (lo, end))
                while True:
                    rows = wcur.fetchmany(BATCH)
                    if not rows: break
                    dc.executemany(ins, rows); dst.commit(); got += len(rows)
                    for r in rows:
                        for v in r:
                            if isinstance(v, (bytes, str)): wb += len(v)
                ok = True; break
            except Exception as e:
                log(f"  {tbl} [{lo},{end}) fetch attempt{attempt}/{FETCH_RETRIES} FAIL: {type(e).__name__}: {str(e)[:120]}")
                if attempt < FETCH_RETRIES: time.sleep(5)
            finally:
                try:
                    if wcur: wcur.close()
                    if wf: wf.close()
                except Exception: pass
        if not ok:
            log(f"  {tbl}: window [{lo},{end}) fetch gave up after {FETCH_RETRIES} attempts, STOP table"); break
        wno += 1; gbytes += wb; ggot += got
        state[tbl] = {'last': end, 'done': False}; save_state()
        log(f"  {tbl} w{wno}: [{lo},{end}) got={got:,} +{wb/1024/1024:.0f}MB tot={ggot:,}行 {gbytes/1024/1024/1024:.1f}GB {gbytes/(time.time()-t0)/1024/1024:.1f}MB/s")
        lo = end
    if lo > max_id:
        state[tbl] = {'last': max_id + 1, 'done': True}; save_state()
    dc.execute(f"SELECT COUNT(*) FROM `{tbl}`"); ln = dc.fetchone()[0]
    log(f"DONE {tbl}: local={ln:,} windows={wno} {gbytes/1024/1024/1024:.1f}GB {(time.time()-t0)/3600:.1f}h")
    dst.close()

if __name__ == '__main__':
    log(f"==== BIG CHUNKED start: {len(BIG)} tables window={WINDOW_ROWS} retries={FETCH_RETRIES} read_to={READ_TIMEOUT} ====")
    for t in BIG:
        try: load_chunked(t)
        except Exception as e:
            log(f"FAIL {t}: {type(e).__name__}: {str(e)[:250]}")
    log(f"==== BIG CHUNKED end ====")
    LOG.close()
