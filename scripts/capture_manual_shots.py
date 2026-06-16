"""
截取 MetaProfile 前端各功能页与关键交互，供《软件用户手册》贴图。

前置：frontend:80 已 healthy（docker compose up）。
输出：docs/manual_shots/*.png

策略：每页 wait networkidle 后截整页；画像页尝试点开详情抽屉、切换关联图谱 Tab、
点节点跨画像跳转。失败不中断，记录到 log。
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "manual_shots"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost"
VIEWPORT = {"width": 1440, "height": 900}

log: list[str] = []


def shot(page, name: str, full: bool = False) -> None:
    p = OUT / f"{name}.png"
    page.screenshot(path=str(p), full_page=full)
    log.append(f"  OK  {name}.png")


def goto(page, path: str) -> None:
    page.goto(f"{BASE}/{path}")
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(600)


def safe(page, fn, label: str) -> None:
    try:
        fn()
        log.append(f"  OK  {label}")
    except Exception as e:
        log.append(f"  --  skip {label}: {type(e).__name__}")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT, locale="zh-CN")
        page = ctx.new_page()

        # ---- 基础九页 ----
        pages = [
            ("dashboard", "01_dashboard"),
            ("tech", "02_tech_list"),
            ("project", "03_project_list"),
            ("org", "04_org_list"),
            ("person", "05_person_list"),
            ("scan", "06_scan"),
            ("discovery", "07_discovery"),
            ("topics", "08_topics"),
            ("settings", "09_settings"),
        ]
        for path, name in pages:
            log.append(f"[{name}] /{path}")
            goto(page, path)
            safe(page, lambda: shot(page, name, full=True), f"shot {name}")

        # ---- 系统配置三 Tab ----
        log.append("[settings_tabs]")
        goto(page, "settings")
        for i, tab in enumerate(["数据源配置", "采集任务"], start=1):
            def _click(t=tab):
                page.get_by_role("tab", name=t).click(timeout=3000)
                page.wait_for_timeout(400)
                shot(page, f"09b_settings_tab{i}")
            safe(page, _click, f"settings tab {tab}")

        # ---- 技术画像详情抽屉 + 关联图谱 + 跨画像跳转 ----
        log.append("[tech_detail]")
        goto(page, "tech")

        def open_first_detail():
            # 优先「详情」按钮，其次双击首行
            btn = page.get_by_role("button", name="详情").first
            try:
                btn.click(timeout=4000)
            except Exception:
                page.locator("tr").nth(1).dblclick(timeout=4000)
            page.wait_for_timeout(1000)
            shot(page, "10_tech_detail_drawer", full=True)
        safe(page, open_first_detail, "open tech detail drawer")

        def graph_tab():
            # 抽屉内 Tab：关联图谱
            page.get_by_role("tab", name="关联图谱").click(timeout=4000)
            page.wait_for_timeout(1500)
            shot(page, "11_tech_relation_graph", full=True)
        safe(page, graph_tab, "switch to relation graph")

        def cross_jump():
            # 点图谱中首个可跳节点（SVG/G6 canvas 节点）
            canvas = page.locator("canvas").first
            box = canvas.bounding_box()
            if not box:
                raise RuntimeError("no canvas")
            # 点击偏离中心的相邻节点
            page.mouse.click(box["x"] + box["width"] * 0.72, box["y"] + box["height"] * 0.3)
            page.wait_for_timeout(1500)
            shot(page, "12_cross_profile_jump", full=True)
        safe(page, cross_jump, "cross-profile jump")

        # ---- 选题服务详情抽屉 ----
        log.append("[topic_detail]")
        goto(page, "topics")

        def topic_detail():
            page.get_by_role("button", name="详情").first.click(timeout=4000)
            page.wait_for_timeout(1000)
            shot(page, "13_topic_detail", full=True)
        safe(page, topic_detail, "open topic detail")

        # ---- 扫描监测详情抽屉 ----
        log.append("[scan_detail]")
        goto(page, "scan")

        def scan_detail():
            page.get_by_role("button", name="详情").first.click(timeout=4000)
            page.wait_for_timeout(1000)
            shot(page, "14_scan_detail", full=True)
        safe(page, scan_detail, "open scan detail")

        browser.close()

    print("\n".join(log))
    files = sorted(OUT.glob("*.png"))
    print(f"\n=== {len(files)} screenshots in {OUT} ===")
    for f in files:
        print(f"  {f.name}  {f.stat().st_size//1024} KB")


if __name__ == "__main__":
    sys.exit(main())
