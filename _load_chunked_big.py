import pymysql, time, io, threading, json, os
from pymysql.cursors import SSCursor

# 大表分块灌:绕 Doris workgroup(normal,11GB)内存墙。market/patent 全表扫单查询吃31GB必OOM。
# 策略:按 id 区间分窗,每窗<=WINDOW_ROWS行(控单查询内存<11GB),COUNT二分定窗上界;
#       每窗 DELETE[id,hi)+INSERT 幂等(本地 Doris 无 IGNORE),每窗存last=真续传不重读。
# 2026-06-17 抗silent-stall:VPN/代理路径~30min静默断流(read_timeout=86400→pymysql傻等24h)。
#   解:①每窗全新rc+wf连接(不带stalled socket);②read_timeout=600(stall 10min内报错);
#       ③每窗fetch重试3次(INSERT IGNORE幂等,重连重取自愈);④WINDOW_ROWS=500K(每窗~15min<<30min阈值)。
BATCH = 5000
WINDOW_ROWS = 50_000           # 2026-06-20:500K 大窗被远端中途掐(WinError10054/InterfaceError0);缩到50K,每窗扫描小到能在被杀前传完
BISECT_MAX_ITERS = 35
READ_TIMEOUT = 600             # 单次socket读最长秒数;stall(无数据)>此值即报错,触发重试
FETCH_RETRIES = 3              # 每窗fetch重试次数
REMOTE = dict(host='10.242.0.1', port=9030, user='gz_kt5', password='92f5IRTld93lDPKYZZ5p',
              database='ods_zbzx', charset='utf8mb4', connect_timeout=10, read_timeout=86400)
# 2026-06-18: 迁到本地 Doris(9030 root 无密码)。原 mp-mysql:3307 已废弃删除。
LOCAL = dict(host='127.0.0.1', port=9030, user='root', password='',
             database='ods_zbzx', charset='utf8mb4', connect_timeout=10)
# big3 放开(2026-06-18):science 已灌完(5.58M)。云端 company 414M 封 10M;market/patent 各 20% 抽样(设计 B)。
# 顺序:已验证的 market/patent 先;company 用 company_id 是新路径放最后兜底
BIG = ['ods_market_analysis_cn', 'ods_invention_patent_cn', 'ods_company_basic_info']
SAMPLE_CAP = {
    "ods_company_basic_info": 10_000_000,   # 414M → 10M(~2.4%)
    "ods_market_analysis_cn":  7_280_000,   # 36.4M → 20%
    "ods_invention_patent_cn": 5_900_000,   # 29.5M → 20%
}
# company 无 `id` 列(PK=company_id);其余大表均以 id 分窗。
KEY_COL = {"ods_company_basic_info": "company_id"}

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

def bisect_end(rcur, tbl, key, lo, max_id, target):
    a, b = lo + 1, max_id + 1; best = lo + 1
    for _ in range(BISECT_MAX_ITERS):
        if b - a <= 1: break
        mid = (a + b) // 2
        rcur.execute(f"SELECT COUNT(*) FROM `{tbl}` WHERE `{key}`>={lo} AND `{key}`<{mid}")
        c = rcur.fetchone()[0]
        if c <= target: best = mid; a = mid
        else: b = mid
    return best

def load_chunked(tbl):
    if state.get(tbl, {}).get('done'):
        log(f"SKIP {tbl}: done"); return
    key = KEY_COL.get(tbl, 'id')
    rc, rcur = conn_remote()
    rcur.execute(f"SELECT MIN(`{key}`), MAX(`{key}`) FROM `{tbl}`")
    min_id, max_id = rcur.fetchone(); rc.close()
    if min_id is None:
        log(f"SKIP {tbl}: empty on remote"); return
    lo = state.get(tbl, {}).get('last', min_id)
    dst = pymysql.connect(**LOCAL); dc = dst.cursor(); dc.execute("SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'")
    dc.execute(f"SELECT COUNT(*) FROM `{tbl}`"); have = dc.fetchone()[0]
    log(f"START {tbl}: id[{min_id},{max_id}] resume_from={lo} local已有{have:,}行")
    collist = ins = None; wno = 0; t0 = time.time(); gbytes = 0; ggot = 0
    while lo <= max_id:
        # 整窗(bisect+取数)无限重试+指数退避:隧道抖断时等待自愈,不放弃本表。
        # 窗口 DELETE+INSERT 幂等,整窗重跑严格无重复。
        attempt = 0; end = None; got = 0; wb = 0
        while True:
            attempt += 1
            rc = wf = wcur = None
            try:
                # ── bisect 定窗上界(每窗全新 rc,防复用 stalled socket) ──
                rc, rcur = conn_remote()
                try:
                    end = bisect_end(rcur, tbl, key, lo, max_id, WINDOW_ROWS)
                    rcur.execute(f"SELECT COUNT(*) FROM `{tbl}` WHERE `{key}`>={lo} AND `{key}`<{end}")
                    c = rcur.fetchone()[0]
                    if end <= lo or c == 0:
                        rcur.execute(f"SELECT MIN(`{key}`) FROM `{tbl}` WHERE `{key}`>={lo}")
                        nid = rcur.fetchone()[0]
                        if nid is None:
                            log(f"  {tbl}: no rows>= {lo}"); end = None
                            break
                        end = nid + 1
                finally:
                    rc.close()
                # ── 流式取数 + DELETE+INSERT 幂等 ──
                got = 0; wb = 0
                wf, wcur = conn_remote(stream=True)
                wcur.execute(f"SELECT * FROM `{tbl}` WHERE `{key}`>={lo} AND `{key}`<{end}")
                if collist is None:
                    collist = ",".join(f"`{d[0]}`" for d in wcur.description)
                    ins = f"INSERT INTO `{tbl}` ({collist}) VALUES ({','.join(['%s']*len(wcur.description))})"
                # Doris 无 INSERT IGNORE → 取数前 DELETE 整窗 [lo,end) 再 INSERT;重跑同窗无重复
                dc.execute(f"DELETE FROM `{tbl}` WHERE `{key}` >= %s AND `{key}` < %s", (lo, end))
                while True:
                    rows = wcur.fetchmany(BATCH)
                    if not rows: break
                    dc.executemany(ins, rows); dst.commit(); got += len(rows)
                    for r in rows:
                        for v in r:
                            if isinstance(v, (bytes, str)): wb += len(v)
                try:
                    wcur.close(); wf.close()
                except Exception: pass
                break  # 整窗成功,跳出重试
            except Exception as e:
                backoff = min(120, 5 * (2 ** (attempt - 1)))   # 5,10,20,40,80,120,120...
                log(f"  {tbl} [{lo},{end}) retry#{attempt} FAIL {type(e).__name__}: {str(e)[:90]}; {backoff}s 后重试")
                try:
                    if wcur: wcur.close()
                    if wf: wf.close()
                except Exception: pass
                time.sleep(backoff)
        if end is None:
            break  # no rows 分支
        wno += 1; gbytes += wb; ggot += got
        cap = SAMPLE_CAP.get(tbl)
        if cap and ggot >= cap:
            log(f"  {tbl}: 达抽样封顶 {cap:,} 行(实灌 {ggot:,}),停止本表抽样")
            state[tbl] = {'last': end, 'done': True, 'sampled': True}; save_state()
            lo = max_id + 1
            break
        state[tbl] = {'last': end, 'done': False}; save_state()
        log(f"  {tbl} w{wno}: [{lo},{end}) got={got:,} +{wb/1024/1024:.0f}MB tot={ggot:,}行 {gbytes/1024/1024/1024:.1f}GB {gbytes/(time.time()-t0)/1024/1024:.1f}MB/s")
        lo = end
    if lo > max_id:
        state[tbl] = {'last': max_id + 1, 'done': True}; save_state()
    dc.execute(f"SELECT COUNT(*) FROM `{tbl}`"); ln = dc.fetchone()[0]
    log(f"DONE {tbl}: local={ln:,} windows={wno} {gbytes/1024/1024/1024:.1f}GB {(time.time()-t0)/3600:.1f}h")
    dst.close()

if __name__ == '__main__':
    import sys
    run = sys.argv[1:] if len(sys.argv) > 1 else BIG
    log(f"==== BIG CHUNKED start: {len(run)} tables {run} window={WINDOW_ROWS} backoff=inf read_to={READ_TIMEOUT} ====")
    for t in run:
        try: load_chunked(t)
        except Exception as e:
            log(f"FAIL {t}: {type(e).__name__}: {str(e)[:250]}")
    log(f"==== BIG CHUNKED end ====")
    LOG.close()
