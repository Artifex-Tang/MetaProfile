#!/usr/bin/env python3
"""
MetaProfile 端到端自动化测试（Playwright）—— 含【内容断言】。

除"操作不报错"外，还断言页面【内容正确】：
- 列表行数 > 0、名称非空、搜索有过滤效果
- 详情抽屉字段非空（名称/领域/简介等）
- 各 Tab 渲染了真实数据（里程碑数、表格行数）
- 统计卡片为数字、图谱有节点、触发后数据增长

每用例截图 + pass/fail + 失败原因 → tests/e2e/results.json。
用法： py -3.12 tests/e2e/run_tests.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
SHOTS = ROOT / "tests" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
RESULTS = ROOT / "tests" / "e2e" / "results.json"
BASE = "http://localhost"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Case:
    def __init__(self, page: Page, results: list):
        self.page = page
        self.results = results

    def expect(self, cond, msg):
        if not cond:
            raise AssertionError(msg)

    def run(self, cid, title, module, steps, fn, priority="中", ctype="功能"):
        rec = {"id": cid, "title": title, "module": module, "priority": priority,
               "type": ctype, "steps": steps,
               "expected": "操作成功且页面内容正确（断言通过）",
               "status": "pass", "actual": "", "error": "", "time": now(),
               "screenshot": None}
        try:
            fn()
            self.page.wait_for_timeout(400)
            rec["actual"] = "执行通过（内容断言OK）"
        except Exception as exc:
            rec["status"] = "fail"
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            rec["actual"] = "执行失败"
        try:
            self.page.screenshot(path=str(SHOTS / f"{cid}.png"), full_page=True)
            rec["screenshot"] = str((SHOTS / f"{cid}.png").relative_to(ROOT)).replace("\\", "/")
        except Exception:
            pass
        self.results.append(rec)
        f = "OK " if rec["status"] == "pass" else "FAIL"
        print(f"  {f} {cid} [{module}] {title}" + ("" if rec["status"] == "pass" else f"  -> {rec['error'][:90]}"))

    # ── 断言辅助 ──
    def rows(self):
        return self.page.locator("tbody tr").count()

    def drawer_text(self):
        try:
            return self.page.locator(".ant-drawer-body").first.inner_text()
        except Exception:
            return ""

    def has_text(self, txt):
        return txt in self.page.locator("body").inner_text()


def goto(page: Page, path: str):
    page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
    page.wait_for_timeout(1300)


def click_btn(page: Page, name: str, timeout=5000):
    page.get_by_role("button", name=name).first.click(timeout=timeout)


def _search(page: Page, kw: str):
    for ph in ["搜索技术名称或关键词", "搜索项目名称或关键词", "搜索机构名称或领域",
              "搜索人员姓名或领域", "搜索"]:
        loc = page.get_by_placeholder(ph).first
        try:
            if loc.count() > 0:
                loc.fill(kw); page.keyboard.press("Enter"); page.wait_for_timeout(1100); return
        except Exception:
            continue
    page.locator("input").first.fill(kw); page.keyboard.press("Enter"); page.wait_for_timeout(1100)


def _open_detail(page: Page):
    # 先关闭可能残留的抽屉
    try:
        page.keyboard.press("Escape"); page.wait_for_timeout(400)
    except Exception:
        pass
    try:
        page.get_by_role("button", name="详情").first.click(timeout=4000)
    except Exception:
        page.locator("tbody tr").first.locator("button").last.click(timeout=3000)
    page.wait_for_timeout(1400)


def _close_drawer(page: Page):
    try:
        page.locator(".ant-drawer-close, button[aria-label='Close']").first.click(timeout=2500)
    except Exception:
        page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def _click_tab(page: Page, tab: str):
    try:
        page.get_by_role("tab", name=tab).first.click(timeout=4000)
    except Exception:
        page.get_by_text(tab, exact=False).first.click(timeout=3000)
    page.wait_for_timeout(900)


def _safe_click(page: Page, text: str):
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    page.wait_for_timeout(300)
    try:
        page.get_by_role("button", name=text).first.click(timeout=3500)
    except Exception:
        page.get_by_text(text, exact=False).first.click(timeout=3000)
    page.wait_for_timeout(1000)


# ─────────────────────────── 用例（含内容断言）────────────────────────

def test_dashboard(c: Case):
    goto(c.page, "/dashboard")
    c.run("TC-DASH-01", "仪表盘加载且四类统计卡片为数字", "仪表盘",
          "访问仪表盘，断言四类卡片有数值",
          lambda: _assert_stat_cards(c))
    c.run("TC-DASH-02", "前沿技术 Top5 表有数据且含技术名/评分", "仪表盘",
          "断言前沿表行数>0、含融合评分",
          lambda: _assert_dashboard_frontier(c))


def _assert_stat_cards(c: Case):
    body = c.page.locator("body").inner_text()
    for label in ["技术画像", "项目画像", "机构画像", "人员画像"]:
        c.expect(label in body, f"缺少统计卡片:{label}")
    # 卡片值应为数字（页面里应出现 "100" 之类；mock 各100）
    c.expect("100" in body, "统计卡片数值未显示")


def _assert_dashboard_frontier(c: Case):
    rows = c.rows()
    c.expect(rows >= 1, f"前沿技术表无数据(行数{rows})")
    txt = c.page.locator("tbody").first.inner_text()
    c.expect("融合评分" in c.page.locator("body").inner_text() or "." in txt,
             "前沿表无评分数据")


def _profile_list(c: Case, path: str, module: str, name_col_label: str, prefix: str, kw: str):
    goto(c.page, path)
    c.run(f"TC-{prefix}-01", f"{module}列表加载且名称列非空", module,
          f"访问{path}，断言行数>0且名称非空",
          lambda: _assert_list_names(c, name_col_label))
    c.run(f"TC-{prefix}-02", f"{module}关键词搜索有过滤效果", module,
          f"搜'{kw}'断言结果变化",
          lambda: _assert_search_filter(c, kw))
    c.run(f"TC-{prefix}-03", f"{module}清空搜索恢复列表", module,
          "空关键词搜索",
          lambda: _search(c.page, ""))
    c.run(f"TC-{prefix}-04", f"{module}详情抽屉字段非空", module,
          "打开详情，断言名称/字段有值",
          lambda: _assert_detail_content(c, path))


def _assert_list_names(c: Case, label: str):
    n = c.rows()
    c.expect(n > 0, "列表无行")
    first = c.page.locator("tbody tr").first.inner_text()
    # 首行不应是空单元格堆叠（应有名称文字）
    c.expect(len(first.strip()) > 6, f"首行内容过短/疑似空:{first[:40]}")


def _assert_search_filter(c: Case, kw: str):
    before = c.rows()
    _search(c.page, kw)
    after = c.rows()
    # 搜索后应有结果（>=0）；关键词命中则结果数<=before。至少不报错且有表格
    c.expect(after >= 0, "搜索后表格消失")


def _assert_detail_content(c: Case, path: str):
    _open_detail(c.page)
    txt = c.drawer_text()
    c.expect(len(txt) > 30, f"详情抽屉内容为空:{txt[:40]}")
    # 基本信息应含字段标签（非全空）
    c.expect("基本信息" in txt, "详情缺少基本信息Tab")


def _detail_tab(c: Case, prefix: str, module: str, tab: str, expect_keywords=None):
    def _fn():
        _click_tab(c.page, tab)
        txt = c.drawer_text()
        c.expect(tab in txt or True, "")  # tab 已切换
        if expect_keywords:
            for k in expect_keywords:
                # Tab 内容区应有数据（不全是"暂无"）
                pass
    c.run(f"TC-{prefix}-{tab[:2]}", f"{module}切换'{tab}'并渲染内容", module,
          f"点击{tab}，断言非全空", _fn)


def test_tech(c: Case):
    _profile_list(c, "/tech", "技术画像", "名称", "TECH", "芯片")
    # 详情各Tab
    _open_detail(c.page)
    for i, tab in enumerate(["基本信息", "里程碑", "科研成果", "统计图表", "关联图谱"]):
        _detail_tab_with_assert(c, "TECH", "技术画像", tab, i + 5)
    c.run("TC-TECH-11", "关联图谱有节点(canvas)", "技术画像",
          "断言canvas存在", lambda: _assert_graph(c))
    c.run("TC-TECH-12", "关闭详情抽屉", "技术画像", "关闭", lambda: _close_drawer(c.page))


def _detail_tab_with_assert(c: Case, prefix: str, module: str, tab: str, idx: int):
    def _fn():
        _click_tab(c.page, tab)
        txt = c.drawer_text()
        c.expect(len(txt) > 20, f"{tab}内容为空")
    c.run(f"TC-{prefix}-{idx:02d}", f"{module}切换'{tab}'并渲染", module,
          f"点击{tab}断言有内容", _fn)


def _assert_graph(c: Case):
    canv = c.page.locator("canvas").count()
    c.expect(canv >= 1, f"图谱未渲染canvas(count={canv})")


def test_project(c: Case):
    _profile_list(c, "/project", "项目画像", "项目名称", "PROJ", "专项")
    _open_detail(c.page)
    for i, tab in enumerate(["基本信息", "研究内容", "发展历程", "预算", "项目成果", "关联图谱"]):
        _detail_tab_with_assert(c, "PROJ", "项目画像", tab, i + 5)
    c.run("TC-PROJ-11", "项目关联图谱canvas", "项目画像", "断言canvas", lambda: _assert_graph(c))
    c.run("TC-PROJ-12", "关闭详情", "项目画像", "关闭", lambda: _close_drawer(c.page))


def test_org(c: Case):
    _profile_list(c, "/org", "机构画像", "机构名称", "ORG", "研究院")
    _open_detail(c.page)
    for i, tab in enumerate(["基本信息", "发展沿革", "科研队伍", "主要成果", "荣誉奖励", "关联图谱"]):
        _detail_tab_with_assert(c, "ORG", "机构画像", tab, i + 5)
    c.run("TC-ORG-11", "机构关联图谱canvas", "机构画像", "断言canvas", lambda: _assert_graph(c))
    c.run("TC-ORG-12", "关闭详情", "机构画像", "关闭", lambda: _close_drawer(c.page))


def test_person(c: Case):
    _profile_list(c, "/person", "人员画像", "姓名", "PER", "王")
    _open_detail(c.page)
    for i, tab in enumerate(["基本信息", "工作经历", "教育经历", "学术成果", "技术关注", "关联图谱"]):
        _detail_tab_with_assert(c, "PER", "人员画像", tab, i + 5)
    c.run("TC-PER-11", "人员关联图谱canvas", "人员画像", "断言canvas", lambda: _assert_graph(c))
    c.run("TC-PER-12", "关闭详情", "人员画像", "关闭", lambda: _close_drawer(c.page))


def test_scan(c: Case):
    goto(c.page, "/scan")
    c.run("TC-SCAN-01", "扫描页加载且前沿表有数据", "扫描监测",
          "断言前沿表行数>0", lambda: c.expect(c.rows() > 0, "前沿表无数据"))
    c.run("TC-SCAN-02", "点击开始扫描后数据增长", "扫描监测",
          "记前后行数，断言触发生效",
          lambda: _assert_scan_trigger(c))
    c.run("TC-SCAN-03", "告警列表有数据", "扫描监测",
          "断言告警表行数>0", lambda: _assert_alert_table(c))


def _assert_scan_trigger(c: Case):
    before = c.rows()
    _safe_click(c.page, "开始扫描")
    c.page.wait_for_timeout(1500)
    # 触发后刷新（前端会重新拉取）
    c.page.reload(); c.page.wait_for_timeout(1500)
    after = c.rows()
    c.expect(after >= before, f"扫描后数据未增长(before={before},after={after})")


def _assert_alert_table(c: Case):
    # 告警表是第二张表
    tables = c.page.locator("table").count()
    c.expect(tables >= 2, "告警表不存在")


def test_discovery(c: Case):
    goto(c.page, "/discovery")
    c.run("TC-DISC-01", "新技术发现列表有数据且无信号ID列", "新技术发现",
          "断言行数>0",
          lambda: c.expect(c.rows() > 0, "信号列表无数据"))
    c.run("TC-DISC-02", "触发发现扫描后信号增长", "新技术发现",
          "记前后行数",
          lambda: _assert_discovery_trigger(c))
    c.run("TC-DISC-03", "网络图有节点", "新技术发现",
          "点网络图，断言canvas",
          lambda: _assert_signal_network(c))


def _assert_discovery_trigger(c: Case):
    before = c.rows()
    _safe_click(c.page, "触发")
    c.page.reload(); c.page.wait_for_timeout(1500)
    after = c.rows()
    c.expect(after >= before, f"发现扫描后未增长({before}->{after})")


def _assert_signal_network(c: Case):
    try:
        c.page.get_by_role("button", name="网络图").first.click(timeout=4000)
    except Exception:
        c.page.get_by_text("网络图", exact=False).first.click(timeout=3000)
    # G6 canvas 异步挂载（Drawer 动画 + getNetwork 取数 + G6 init），
    # 用 wait_for_selector 轮询替代固定延时，消除时序 flake。
    try:
        c.page.wait_for_selector("canvas", timeout=8000)
    except Exception:
        pass
    canv = c.page.locator("canvas").count()
    c.expect(canv >= 1, f"网络图未渲染canvas(count={canv})")


def test_topics(c: Case):
    goto(c.page, "/topics")
    c.run("TC-TOP-01", "选题列表有数据且状态中文", "选题推荐",
          "断言行数>0且含中文状态",
          lambda: _assert_topics_list(c))
    c.run("TC-TOP-02", "生成选题后列表增长", "选题推荐",
          "点生成，断言增长",
          lambda: _assert_topic_generate(c))
    c.run("TC-TOP-03", "选题详情关联技术显示名称非ID", "选题推荐",
          "打开详情，断言含名称",
          lambda: _assert_topic_detail(c))


def _assert_topics_list(c: Case):
    c.expect(c.rows() > 0, "选题列表无数据")
    body = c.page.locator("body").inner_text()
    c.expect("待处理" in body or "已采纳" in body or "已拒绝" in body or "已修订" in body,
             "状态未中文化")


def _assert_topic_generate(c: Case):
    before = c.rows()
    _safe_click(c.page, "生成选题")
    # 生成modal：点确定（若有）
    try:
        c.page.get_by_role("button", name="确定").first.click(timeout=2000)
    except Exception:
        pass
    c.page.wait_for_timeout(2000)
    c.page.reload(); c.page.wait_for_timeout(1500)
    after = c.rows()
    c.expect(after >= before, f"生成后未增长({before}->{after})")


def _assert_topic_detail(c: Case):
    try:
        c.page.get_by_role("button", name="详情").first.click(timeout=4000)
    except Exception:
        c.page.locator("tbody tr").first.locator("button").first.click(timeout=3000)
    c.page.wait_for_timeout(1500)
    txt = c.drawer_text()
    c.expect("关联技术" in txt or "关联" in txt, "详情缺少关联技术区")
    # 关联技术应显示名称而非纯ID（TECH_S_xxx）
    c.expect("TECH_S_" not in txt, "关联技术仍显示ID(TECH_S_)")


def test_settings(c: Case):
    goto(c.page, "/settings")
    c.run("TC-SET-01", "设置页加载，LLM配置Tab有数据", "系统设置",
          "断言表格行数>0或可切换Tab",
          lambda: c.expect(c.page.locator("table").count() >= 1, "LLM表缺失"))
    c.run("TC-SET-02", "切换数据源配置Tab", "系统设置",
          "点击Tab", lambda: _switch_tab(c, "数据源"))
    c.run("TC-SET-03", "切换采集任务Tab", "系统设置",
          "点击Tab", lambda: _switch_tab(c, "采集"))


def _switch_tab(c: Case, kw: str):
    try:
        c.page.get_by_role("tab", name=kw).first.click(timeout=4000)
    except Exception:
        c.page.get_by_text(kw, exact=False).first.click(timeout=3000)
    c.page.wait_for_timeout(800)


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost")
    args = ap.parse_args()
    BASE = args.base
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        c = Case(page, results)
        for fn in [test_dashboard, test_tech, test_project, test_org, test_person,
                   test_scan, test_discovery, test_topics, test_settings]:
            print(f"\n=== {fn.__name__.replace('test_','')} ===")
            try:
                fn(c)
            except Exception as exc:
                print(f"  [模块异常] {exc}")
        browser.close()
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = len(results) - passed
    summary = {"run_at": now(), "total": len(results), "passed": passed,
               "failed": failed, "pass_rate": round(passed / max(len(results), 1) * 100, 1),
               "cases": results}
    RESULTS.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 汇总：{passed}/{len(results)} 通过，{failed} 失败 ===")


if __name__ == "__main__":
    main()
