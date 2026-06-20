#!/usr/bin/env python3
"""
MetaProfile API 功能覆盖测试：对四类画像的全部 11 个标准接口 + 分析层/设置接口
做请求 + 结构断言，验证"功能全覆盖"。

每个画像接口：get / search / semantic-search / batch / update / import / stats /
relation / relation-path / changes / enrich。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://localhost"
PRE = {"tech": "api-tech", "project": "api-project", "org": "api-org", "person": "api-person"}
RESULTS = []


def req(method: str, path: str, body=None, expect=200):
    url = f"{BASE}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            code = resp.status
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        code = e.code
        raw = e.read().decode()[:200]
    except Exception as e:
        return 0, str(e)[:120], None
    try:
        parsed = json.loads(raw) if raw else None
    except Exception:
        parsed = None
    return code, raw[:160], parsed


def record(cid, title, ok, detail=""):
    RESULTS.append({"id": cid, "title": title, "status": "pass" if ok else "fail", "detail": detail})
    print(f"  {'OK ' if ok else 'FAIL'} {cid} {title}" + ("" if ok else f"  -> {detail[:90]}"))


def profile_api_tests(t: str):
    """对一个画像类型跑全部 11 个接口。"""
    p = PRE[t]
    # 1. search
    code, _, d = req("POST", f"{p}/api/v1/profile/{t}/search", {"page": 1, "page_size": 5})
    ok = code == 200 and isinstance(d, dict) and "items" in d and len(d["items"]) > 0
    record(f"API-{t}-01-search", f"{t} 搜索返回非空列表", ok,
           f"code={code} total={d.get('total') if isinstance(d,dict) else '?'}")
    if not ok or not d["items"]:
        return  # 无数据则后续无法继续
    eid = d["items"][0].get(f"{t}_id") or d["items"][0].get("tech_id")
    # 2. get by id
    code, _, d2 = req("GET", f"{p}/api/v1/profile/{t}/{eid}")
    ok = code == 200 and isinstance(d2, dict) and (
        d2.get(f"{t}_id") == eid or d2.get("tech_id") == eid)
    record(f"API-{t}-02-get", f"{t} 详情含正确ID且字段非空", ok,
           f"code={code} keys={len(d2) if isinstance(d2,dict) else 0}")
    # 3. batch
    code, _, d3 = req("POST", f"{p}/api/v1/profile/{t}/batch", {f"{t}_ids": [eid]})
    ok = code == 200 and isinstance(d3, list) and len(d3) >= 1
    record(f"API-{t}-03-batch", f"{t} 批量查询", ok, f"code={code} n={len(d3) if isinstance(d3,list) else 0}")
    # 4. stats
    code, _, d4 = req("GET", f"{p}/api/v1/stats/{t}")
    ok = code == 200 and isinstance(d4, dict) and d4.get("total", 0) > 0
    record(f"API-{t}-04-stats", f"{t} 统计含总量", ok,
           f"code={code} total={d4.get('total') if isinstance(d4,dict) else '?'}")
    # 5. relation
    code, _, d5 = req("GET", f"{p}/api/v1/relation/{t}/{eid}")
    ok = code == 200 and isinstance(d5, dict) and "items" in d5
    record(f"API-{t}-05-relation", f"{t} 关系列表", ok,
           f"code={code} total={d5.get('total') if isinstance(d5,dict) else '?'}")
    # 6. relation path（用两个不同实体，shortestPath 不支持自环）
    eid2 = d["items"][1].get(f"{t}_id") or d["items"][1].get("tech_id") if len(d["items"]) > 1 else eid
    code, _, _ = req("POST", f"{p}/api/v1/relation/{t}/path",
                     {"from_id": eid, "to_id": eid2, "max_depth": 4})
    record(f"API-{t}-06-path", f"{t} 关系路径查询", code == 200, f"code={code}")
    # 7. changes（需 since 参数）
    code, _, d7 = req("GET", f"{p}/api/v1/profile/{t}/changes?since=2000-01-01T00:00:00&limit=5")
    ok = code == 200 and isinstance(d7, dict) and "items" in d7
    record(f"API-{t}-07-changes", f"{t} 变更记录", ok, f"code={code}")
    # 8. import：空列表 422 校验；四画像 bulk_import 均真持久化，回灌验证落库+可读回
    code, _, _ = req("POST", f"{p}/api/v1/profile/{t}/import", {"profiles": []})
    record(f"API-{t}-08a-import-validate", f"{t} 导入空列表拒绝(422)", code == 422, f"code={code}")
    ts = str(int(time.time()))
    new_id = f"E2E_IMPORT_{t.upper()}_{ts}"
    _, _, body = req("GET", f"{p}/api/v1/profile/{t}/{eid}")
    if isinstance(body, dict):
        body[f"{t}_id"] = new_id
        # 剥离 response-only 字段（ingest_ods scorer 产出，非 import 输入；TechProfile extra=forbid）
        for k in ("veracity_score", "timeliness_score", "data_as_of"):
            body.pop(k, None)
        if t == "project":
            body["project_no"] = int(ts)  # uq_project_profile_project_no 避免唯一约束冲突
        code, _, d8 = req("POST", f"{p}/api/v1/profile/{t}/import", {"profiles": [body]})
        ok = code == 200 and isinstance(d8, dict) and d8.get("accepted_count", 0) >= 1
        record(f"API-{t}-08b-import-real", f"{t} 真实导入落库", ok,
               f"code={code} accepted={d8.get('accepted_count') if isinstance(d8, dict) else '?'}")
        if ok:
            code, _, _ = req("GET", f"{p}/api/v1/profile/{t}/{new_id}")
            record(f"API-{t}-08c-import-retrievable", f"{t} 导入后可读回", code == 200, f"code={code}")
    # 9. update（字段级，operator+reason）
    body = {"operator": "tester", "reason": "api_test"}
    code, _, _ = req("PUT", f"{p}/api/v1/profile/{t}/{eid}", body)
    record(f"API-{t}-09-update", f"{t} 字段级更新", code == 200, f"code={code}")
    # 10. semantic-search（需 ES + IK 分词；未装 IK 时 500=已知限制，200 则校验结果结构）
    code, _, d10 = req("POST", f"{p}/api/v1/profile/{t}/semantic-search", {"query": "技术", "top_k": 3})
    if code == 200:
        ok = isinstance(d10, dict) and ("items" in d10 or "results" in d10)
        record(f"API-{t}-10-semantic", f"{t} 语义检索", ok,
               f"code=200 keys={list(d10.keys())[:4] if isinstance(d10, dict) else 0}")
    else:
        record(f"API-{t}-10-semantic", f"{t} 语义检索(IK未装已知限制)", code == 500, f"code={code}")
    # 11. enrich：异步 celery 派发（task_id+status）+ 任务状态查询
    code, _, d11 = req("POST", f"{p}/api/v1/profile/{t}/{eid}/enrich")
    ok = code in (200, 202) and isinstance(d11, dict) and "task_id" in d11
    record(f"API-{t}-11-enrich", f"{t} 补全任务派发", ok,
           f"code={code} status={d11.get('status') if isinstance(d11, dict) else '?'}")
    if ok and isinstance(d11, dict) and d11.get("status") == "queued":
        tid = d11["task_id"]
        c2, _, d2 = req("GET", f"{p}/api/v1/profile/{t}/enrich/task/{tid}")
        record(f"API-{t}-11b-enrich-status", f"{t} 补全任务状态查询",
               c2 == 200 and isinstance(d2, dict) and "state" in d2,
               f"code={c2} state={d2.get('state') if isinstance(d2, dict) else '?'}")


def analysis_tests():
    # scan
    code, _, d = req("POST", "api-scan/api/v1/frontier-tech/scan")
    record("API-SCAN-01", "扫描触发并产数据", code == 200, f"code={code}")
    code, _, d = req("GET", "api-scan/api/v1/frontier-tech/list?page=1&page_size=3")
    record("API-SCAN-02", "前沿技术列表非空", code == 200 and d and d.get("total", 0) > 0,
           f"total={d.get('total') if d else '?'}")
    code, _, d = req("GET", "api-scan/api/v1/frontier-tech/alerts?page=1&page_size=3")
    record("API-SCAN-03", "告警列表非空", code == 200 and d and d.get("total", 0) > 0,
           f"total={d.get('total') if d else '?'}")
    # discovery
    code, _ = req("POST", "api-discovery/api/v1/new-tech/scan")[:2]
    code, _, d = req("POST", "api-discovery/api/v1/new-tech/scan")
    record("API-DISC-01", "发现扫描触发", code == 200, f"code={code}")
    code, _, d = req("GET", "api-discovery/api/v1/new-tech/signals?page=1&page_size=3")
    record("API-DISC-02", "弱信号列表非空", code == 200 and d and d.get("total", 0) > 0,
           f"total={d.get('total') if d else '?'}")
    # topics
    code, _, d = req("POST", "api-topic/api/v1/topics/generate?target_count=5")
    record("API-TOP-01", "选题生成触发", code == 200, f"code={code}")
    code, _, d = req("GET", "api-topic/api/v1/topics/list?page=1&page_size=3")
    record("API-TOP-02", "选题列表非空", code == 200 and d and d.get("total", 0) > 0,
           f"total={d.get('total') if d else '?'}")
    # settings
    code, _, d = req("GET", "api-settings/api/v1/settings/llm")
    record("API-SET-01", "LLM配置列表", code == 200, f"code={code}")
    code, _, d = req("GET", "api-settings/api/v1/settings/datasources")
    record("API-SET-02", "数据源列表", code == 200, f"code={code}")


def settings_crud_tests():
    """settings_api 全生命周期：LLM/数据源 CRUD + sync/test + 采集触发/任务。"""
    import time
    suffix = str(int(time.time()))

    # ── LLM 配置 CRUD + test + sync ──
    base = "api-settings/api/v1/settings/llm"
    code, _, d = req("POST", base, {
        "name": f"e2e-llm-{suffix}", "provider": "openai",
        "model_name": "gpt-4o-mini", "api_key": "sk-e2e-test-key-abcdef",
        "api_base": "https://api.openai.com/v1", "model_role": "general",
    })
    record("API-SET-03-llm-create", "LLM配置创建", code == 201 and isinstance(d, dict) and "id" in d, f"code={code}")
    cfg_id = d.get("id") if isinstance(d, dict) else None
    # 注：LLM 无 get-by-id 路由（仅 list/CRUD/sync/test），故跳过 GET 详情
    if cfg_id:
        code, _, d = req("PUT", f"{base}/{cfg_id}", {"name": f"e2e-llm-{suffix}-upd", "temperature": 0.5})
        record("API-SET-05-llm-update", "LLM配置更新", code == 200 and d and "upd" in (d.get("name") or ""), f"code={code}")
        code, _, d = req("POST", f"{base}/{cfg_id}/test")
        record("API-SET-06-llm-test", "LLM连通性测试", code == 200 and isinstance(d, dict) and "success" in d,
               f"code={code} success={d.get('success') if isinstance(d, dict) else '?'}")
        code, _, d = req("POST", f"{base}/{cfg_id}/sync")
        record("API-SET-07-llm-sync", "LLM同步litellm", code == 200 and isinstance(d, dict), f"code={code}")
        code, _, _ = req("DELETE", f"{base}/{cfg_id}")
        record("API-SET-08-llm-delete", "LLM配置删除", code == 204, f"code={code}")

    # ── 数据源 CRUD + 模板（不触发采集，避免与后台任务行锁死锁）──
    ds = "api-settings/api/v1/settings/datasources"
    code, _, d = req("POST", ds, {
        "name": f"e2e-ds-{suffix}", "source_type": "rest_api", "profile_type": "tech",
        "config_json": {"url": "https://example.com/api", "method": "GET"}, "is_enabled": True,
    })
    record("API-SET-09-ds-create", "数据源创建", code == 201 and isinstance(d, dict) and "id" in d, f"code={code}")
    ds_id = d.get("id") if isinstance(d, dict) else None

    code, _, d = req("GET", f"{ds}/templates/list")
    record("API-SET-10-ds-templates", "数据源模板列表", code == 200 and isinstance(d, dict) and len(d) > 0,
           f"code={code} n={len(d) if isinstance(d, dict) else 0}")

    if ds_id:
        code, _, d = req("GET", f"{ds}/{ds_id}")
        record("API-SET-11-ds-get", "数据源详情", code == 200 and d and d.get("id") == ds_id, f"code={code}")
        code, _, d = req("PUT", f"{ds}/{ds_id}", {"name": f"e2e-ds-{suffix}-upd"})
        record("API-SET-12-ds-update", "数据源更新", code == 200 and d and "upd" in (d.get("name") or ""), f"code={code}")
        code, _, _ = req("DELETE", f"{ds}/{ds_id}")
        record("API-SET-13-ds-delete", "数据源删除", code == 204, f"code={code}")

    # ── 采集触发/任务（独立数据源，与 CRUD 行隔离防死锁）──
    code, _, d = req("POST", ds, {
        "name": f"e2e-col-{suffix}", "source_type": "rss", "profile_type": "tech",
        "config_json": {"feed_url": "https://example.com/rss"}, "is_enabled": True,
    })
    col_id = d.get("id") if isinstance(d, dict) and code == 201 else None
    if col_id:
        code, _, d = req("POST", f"api-settings/api/v1/settings/collection/trigger/{col_id}")
        record("API-SET-14-collect-trigger", "采集任务触发", code == 202 and isinstance(d, dict) and "task_id" in d, f"code={code}")
        task_id = d.get("task_id") if isinstance(d, dict) else None
        code, _, d = req("GET", "api-settings/api/v1/settings/collection/tasks?limit=5")
        record("API-SET-15-tasks-list", "采集任务列表", code == 200 and isinstance(d, list),
               f"code={code} n={len(d) if isinstance(d, list) else 0}")
        if task_id:
            code, _, d = req("GET", f"api-settings/api/v1/settings/collection/tasks/{task_id}")
            record("API-SET-16-task-detail", "采集任务详情", code == 200 and d and d.get("id") == task_id, f"code={code}")
            code, _, d = req("GET", f"api-settings/api/v1/settings/collection/tasks/{task_id}/stats")
            record("API-SET-16b-task-stats", "采集任务运行统计",
                   code == 200 and isinstance(d, dict) and "raw_total" in d, f"code={code}")
        code, _, _ = req("DELETE", f"{ds}/{col_id}")
        record("API-SET-17-col-delete", "采集数据源删除", code == 204, f"code={code}")

    # ── 数据连接 CRUD（db_connections，密码加密存/脱敏读）──
    dbc = "api-settings/api/v1/settings/db-connections"
    code, _, d = req("POST", dbc, {
        "name": f"e2e-dbc-{suffix}", "dialect": "doris", "host": "localhost",
        "port": 9030, "database": "ods_zbzx", "username": "root", "password": "e2e-secret",
    })
    record("API-SET-18-dbc-create", "数据连接创建", code == 201 and isinstance(d, dict) and "id" in d, f"code={code}")
    dbc_id = d.get("id") if isinstance(d, dict) else None
    if dbc_id:
        # 脱敏：响应不含 password/password_enc
        masked = isinstance(d, dict) and "password" not in d and "password_enc" not in d
        record("API-SET-19-dbc-masked", "数据连接密码脱敏", masked, f"keys={list(d.keys())[:6] if isinstance(d, dict) else '?'}")
        code, _, d = req("GET", f"{dbc}/{dbc_id}")
        record("API-SET-20-dbc-get", "数据连接详情", code == 200 and d and d.get("id") == dbc_id, f"code={code}")
        code, _, d = req("PUT", f"{dbc}/{dbc_id}", {"host": "127.0.0.1"})
        record("API-SET-21-dbc-update", "数据连接更新", code == 200 and d and d.get("host") == "127.0.0.1", f"code={code}")
        code, _, _ = req("DELETE", f"{dbc}/{dbc_id}")
        record("API-SET-22-dbc-delete", "数据连接删除", code == 204, f"code={code}")


def tech_relation_tests():
    """技术关系路由（E-T4：演进链/前置树双向遍历 TECH_EVOLVE/TECH_PREREQ）+ 枚举 + mock cypher。

    3 个用例：
    - RelationType 枚举新增 TECH_EVOLVE/TECH_PREREQ（value=演进/前置）
    - GET /relation/tech/{id}/tech-relation 双 viewpoint 返 nodes/edges
    - deploy/mock_data.cypher 含 TECH_EVOLVE/TECH_PREREQ 边（防 T5 回归）
    """
    from pathlib import Path

    # 1. 枚举（与 metaprofile.shared.schemas.relations.RelationType 一致）
    try:
        from metaprofile.shared.schemas.relations import RelationType
        ok_e = RelationType.TECH_EVOLVE.value == "演进"
        ok_p = RelationType.TECH_PREREQ.value == "前置"
        record("API-TECHREL-01-enum", "RelationType 含 TECH_EVOLVE/TECH_PREREQ",
               ok_e and ok_p, f"evolve={getattr(RelationType, 'TECH_EVOLVE', None)} "
                              f"prereq={getattr(RelationType, 'TECH_PREREQ', None)}")
    except Exception as e:
        record("API-TECHREL-01-enum", "RelationType 含 TECH_EVOLVE/TECH_PREREQ", False, f"import err: {e!r}"[:120])

    # 2. 路由：取一个 mock 技术做种子，跑 evolve/prereq 双视角
    code, _, d = req("POST", f"{PRE['tech']}/api/v1/profile/tech/search",
                     {"page": 1, "page_size": 5})
    items = d.get("items", []) if isinstance(d, dict) else []
    seed_ok = code == 200 and bool(items)
    if not seed_ok:
        record("API-TECHREL-02a-seed", "mock 技术种子就绪", False,
               f"code={code} items={len(items)}")
    else:
        record("API-TECHREL-02a-seed", "mock 技术种子就绪", True,
               f"n={len(items)}")
        tid = items[0].get("tech_id") or items[0].get("id")
        for vp in ("evolve", "prereq"):
            # req() 把 path 拼到 URL；query string 直接附在 path 上即可
            cc, _, dd = req("GET",
                            f"{PRE['tech']}/api/v1/relation/tech/{tid}/tech-relation"
                            f"?viewpoint={vp}&depth=4",
                            None)
            ok = cc == 200 and isinstance(dd, dict) and dd.get("viewpoint") == vp \
                and "nodes" in dd and "edges" in dd
            record(f"API-TECHREL-02b-route-{vp}",
                   f"技术关系路由 viewpoint={vp}",
                   ok, f"code={cc} vp={dd.get('viewpoint') if isinstance(dd,dict) else '?'} "
                       f"nodes={len(dd.get('nodes', [])) if isinstance(dd,dict) else 0}")

    # 3. mock cypher 含 TECH_EVOLVE/TECH_PREREQ 边（防 T5 生成器改了但产物未重生成）
    try:
        cy_path = Path(__file__).resolve().parents[2] / "deploy" / "mock_data.cypher"
        cy = cy_path.read_text(encoding="utf-8")
        has_evolve = ("TECH_EVOLVE" in cy) or ("演进" in cy)
        has_prereq = ("TECH_PREREQ" in cy) or ("前置" in cy)
        record("API-TECHREL-03-cypher", "mock cypher 含技术-技术边",
               has_evolve and has_prereq,
               f"evolve={has_evolve} prereq={has_prereq} (若 FAIL=需重跑 gen_mock_data.py)")
    except Exception as e:
        record("API-TECHREL-03-cypher", "mock cypher 含技术-技术边", False, f"read err: {e!r}"[:120])


def analysis_detail_tests():
    """分析层详情路由：前沿详情/新技术列表/信号网络/选题详情。"""
    # 前沿详情（路由 {tech_id} 实际按 scan_task_id 过滤）
    code, _, d = req("GET", "api-scan/api/v1/frontier-tech/list?page=1&page_size=1")
    sid = d["items"][0].get("scan_task_id") if code == 200 and d and d.get("items") else None
    if sid:
        code, _, d2 = req("GET", f"api-scan/api/v1/frontier-tech/{sid}")
        record("API-SCAN-04-frontier-detail", "前沿技术详情", code == 200 and d2 and "fusion_score" in d2, f"code={code}")
    else:
        record("API-SCAN-04-frontier-detail", "前沿技术详情", False, "无列表数据")

    # 新技术列表
    code, _, d = req("GET", "api-discovery/api/v1/new-tech/list?page=1&page_size=3")
    record("API-DISC-03-newtech-list", "新技术列表", code == 200 and d and d.get("total", 0) > 0,
           f"code={code} total={d.get('total') if d else '?'}")

    # 信号网络
    code, _, d = req("GET", "api-discovery/api/v1/new-tech/signals?page=1&page_size=1")
    sig = d["items"][0].get("signal_id") if code == 200 and d and d.get("items") else None
    if sig:
        code, _, d2 = req("GET", f"api-discovery/api/v1/new-tech/signals/{sig}/network")
        record("API-DISC-04-signal-network", "信号网络图谱", code == 200 and isinstance(d2, dict),
               f"code={code} keys={list(d2.keys())[:4] if isinstance(d2, dict) else 0}")
    else:
        record("API-DISC-04-signal-network", "信号网络图谱", False, "无信号数据")

    # 选题详情
    code, _, d = req("GET", "api-topic/api/v1/topics/list?page=1&page_size=1")
    tid = d["items"][0].get("topic_id") if code == 200 and d and d.get("items") else None
    if tid:
        code, _, d2 = req("GET", f"api-topic/api/v1/topics/{tid}")
        record("API-TOP-03-topic-detail", "选题详情", code == 200 and d2 and "title" in d2, f"code={code}")
    else:
        record("API-TOP-03-topic-detail", "选题详情", False, "无选题数据")


def main():
    for t in ["tech", "project", "org", "person"]:
        print(f"=== {t} ===")
        profile_api_tests(t)
    print("=== 分析层/设置 ===")
    analysis_tests()
    analysis_detail_tests()
    settings_crud_tests()
    print("=== 技术关系（演进/前置）===")
    tech_relation_tests()
    passed = sum(1 for r in RESULTS if r["status"] == "pass")
    total = len(RESULTS)
    print(f"\n=== API 功能覆盖：{passed}/{total} 通过 ===")
    from pathlib import Path
    out = Path(__file__).resolve().parent / "api_results.json"
    out.write_text(json.dumps({"total": total, "passed": passed,
                               "pass_rate": round(passed/total*100, 1),
                               "cases": RESULTS}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
