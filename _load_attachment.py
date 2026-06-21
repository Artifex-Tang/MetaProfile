import pymysql, time, io, threading, json, os, sys
from pymysql.cursors import SSCursor

# 附件表采样同步 (云 Doris 10.242.0.1 → 本地 Doris 127.0.0.1)。
# 策略:id keyset 前进 (WHERE id>last ORDER BY id LIMIT batch),clean_content/raw_content 有内容即取;
#       SELECT * 全列 (clean+raw+other);Doris MoW (id=unique key) 重插 upsert 幂等;
#       state {table:{last_id,count,done}} 持久 → 中档(5K)跑完,充分档(10K)同脚本 target 续传不重读。
# 用法:python _load_attachment.py [target_rows]   默认 5000
#       target 给大数 (如 10_000_000) 即"尽量多取" → 充分档/小表全量。

BATCH = 1000   # 小批:大 raw 行(52-150KB)×1000=52-150MB/批,稳在 workgroup 11GB 下
READ_TIMEOUT = 600
REMOTE = dict(host='10.242.0.1', port=9030, user='gz_kt5', password='92f5IRTld93lDPKYZZ5p',
              database='ods_zbzx', charset='utf8mb4', connect_timeout=10, read_timeout=86400)
LOCAL = dict(host='127.0.0.1', port=9030, user='root', password='',
             database='ods_zbzx', charset='utf8mb4', connect_timeout=10)

# 8 个有数据的附件表 (_global 全空 / talent clean=0 但 raw 有,纳入靠 raw 过滤)
ATT = [
    'ods_key_events_attachment_cn',
    'ods_financial_info_attachment_cn',
    'ods_industry_report_attachment_cn',
    'ods_international_news_attachment',
    'ods_invention_patent_attachment_cn',
    'ods_science_literature_attachment',
    'ods_strategic_policy_attachment_cn',
    'ods_market_analysis_attachment_cn',
    'ods_talent_info_attachment_cn',   # clean=0 但 raw 有;靠 OR raw 过滤纳入
]

LOG = io.open(r'E:\ccode\MetaProfile\_load_attachment.log', 'a', encoding='utf-8', buffering=1)
lock = threading.Lock()
def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    with lock: print(line, flush=True); LOG.write(line + "\n")

STATE = r'E:\ccode\MetaProfile\_load_attachment_state.json'
slock = threading.Lock()
state = json.load(io.open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {}
def save_state():
    with slock:
        tmp = STATE + '.tmp'; json.dump(state, io.open(tmp, 'w', encoding='utf-8'), ensure_ascii=False); os.replace(tmp, STATE)

def conn_remote(stream=False):
    kw = dict(REMOTE); kw['read_timeout'] = READ_TIMEOUT
    if stream: kw['cursorclass'] = SSCursor
    c = pymysql.connect(**kw); cur = c.cursor()
    try: cur.execute("SET query_timeout=86400")
    except Exception as e: log(f"  SET query_timeout fail {e}")
    # 不设 exec_mem_limit:云 workgroup normal 池~11GB,设 64GB 会被判 workgroup overcommit → FullGC 取消。留默认。
    return c, cur

# 不带 content 过滤:COALESCE/OR 逼云 BE 全扫 text 列 → errCode=2 内存取消。
# 纯 id keyset 取前 N 行(含空 clean 行,真实行;挖掘代码本就 WHERE clean NOT NULL 跳空)。最便宜无 OOM。
# 可选源过滤:ATT_SOURCE=patent_pubscholar 只取该 original_table(equality 廉价,非 text 扫,不 OOM)。
ATT_SOURCE = os.environ.get('ATT_SOURCE', '').strip()
SRC_CLAUSE = f" AND original_table='{ATT_SOURCE}'" if ATT_SOURCE else ""

def load_att(tbl, target):
    skey = f"{tbl}__{ATT_SOURCE}" if ATT_SOURCE else tbl
    st = state.get(skey, {})
    last_id = st.get('last_id', 0)
    have = st.get('count', 0)
    if st.get('done') or have >= target:
        log(f"SKIP {skey}: have={have:,} target={target:,} done={st.get('done')}")
        return
    log(f"START {skey}: have={have:,} target={target:,} resume_id>{last_id}")
    dst = pymysql.connect(**LOCAL); dc = dst.cursor(); dc.execute("SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'")
    ins = None; collist = None; t0 = time.time(); gb = 0; got_total = have
    while got_total < target:
        need = target - got_total
        lim = min(need, BATCH)
        attempt = 0
        rows = None
        while True:  # 单批无限重试+退避 (隧道抖断自愈)
            attempt += 1
            rc = None
            try:
                rc, rcur = conn_remote(stream=True)
                rcur.execute(f"SELECT * FROM `{tbl}` WHERE `id`>{last_id}{SRC_CLAUSE} ORDER BY `id` LIMIT {lim}")
                if ins is None:
                    collist = ",".join(f"`{d[0]}`" for d in rcur.description)
                    ins = f"INSERT INTO `{tbl}` ({collist}) VALUES ({','.join(['%s']*len(rcur.description))})"
                rows = rcur.fetchmany(lim)
                try: rcur.close(); rc.close()
                except Exception: pass
                break
            except Exception as e:
                backoff = min(120, 5 * (2 ** (attempt - 1)))
                log(f"  {tbl} id>{last_id} batch retry#{attempt} FAIL {type(e).__name__}: {str(e)[:80]}; {backoff}s 后重试")
                try:
                    if rc: rc.close()
                except Exception: pass
                time.sleep(backoff)
        if not rows:
            log(f"  {skey}: remote 取尽 (got_total={got_total:,} < target={target:,})")
            state[skey] = {'last_id': last_id, 'count': got_total, 'done': True}; save_state()
            break
        # 幂等写入 (id unique MoW upsert);批量 commit
        wb = 0
        try:
            dc.executemany(ins, rows); dst.commit()
        except Exception as e:
            log(f"  {tbl} 本地 INSERT FAIL {type(e).__name__}: {str(e)[:120]}"); raise
        for r in rows:
            last_id = r[0]  # id 第一列
            for v in r:
                if isinstance(v, (bytes, str)): wb += len(v)
        got_total += len(rows); gb += wb
        state[skey] = {'last_id': last_id, 'count': got_total, 'done': False}; save_state()
        log(f"  {skey} +{len(rows):,} ({wb/1024/1024:.1f}MB) tot={got_total:,}/{target:,} id>{last_id} {gb/1024/1024/(time.time()-t0):.2f}MB/s")
    else:
        # while 正常退出 (达 target),标记 done
        state[skey] = {'last_id': last_id, 'count': got_total, 'done': True}; save_state()
        log(f"DONE {skey}: {got_total:,} rows {gb/1024/1024/1024:.2f}GB {(time.time()-t0)/60:.1f}min")
    dst.close()

if __name__ == '__main__':
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    run = sys.argv[2:] if len(sys.argv) > 2 else ATT
    log(f"==== ATTACHMENT start: target={target:,} tables={len(run)} batch={BATCH} ====")
    for t in run:
        try: load_att(t, target)
        except Exception as e:
            log(f"FAIL {t}: {type(e).__name__}: {str(e)[:250]}")
    log(f"==== ATTACHMENT end ====")
    LOG.close()
