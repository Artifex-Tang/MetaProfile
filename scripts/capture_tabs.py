# -*- coding: utf-8 -*-
"""
补截四画像详情抽屉的每个 Tab，供《软件用户手册v3》贴图。
前置：frontend:80 healthy。对每个画像页打开首条详情，逐个点击已知 Tab 名并截图。
"""
from __future__ import annotations
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "manual_shots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost"

# 画像页 -> (文件前缀, [Tab 名（含默认基本信息）])
PROFILES = {
    "tech": ("tech_tab", ["基本信息", "里程碑", "科研成果", "统计图表", "关联图谱"]),
    "project": ("proj_tab", ["基本信息", "研究内容", "发展历程", "预算明细", "项目成果", "关联图谱"]),
    "org": ("org_tab", ["基本信息", "发展沿革", "科研队伍", "科研设施", "主要成果", "关联图谱"]),
    "person": ("per_tab", ["基本信息", "工作经历", "教育经历", "学术成果", "技术关注", "关联图谱"]),
}
# 索引后缀，避免与既有文件冲突
SUFFIX = {"basic": "basic", "milestone": "ms", "research": "res", "stats": "stat",
          "content": "cnt", "history": "his", "budget": "bud", "results": "res2",
          "evolution": "evo", "team": "team", "facility": "fac", "achievement": "ach",
          "work": "work", "edu": "edu", "academic": "aca", "focus": "foc", "graph": "grp"}
TAB_KEY = {"基本信息": "basic", "里程碑": "milestone", "科研成果": "research", "统计图表": "stats",
           "研究内容": "content", "发展历程": "history", "预算明细": "budget", "项目成果": "results",
           "发展沿革": "evolution", "科研队伍": "team", "科研设施": "facility", "主要成果": "achievement",
           "工作经历": "work", "教育经历": "edu", "学术成果": "academic", "技术关注": "focus",
           "关联图谱": "graph"}

log = []


def shot(page, name, full=True):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    log.append(f"  OK  {name}.png")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
        for path, (prefix, tabs) in PROFILES.items():
            log.append(f"[{path}]")
            page.goto(f"{BASE}/{path}")
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(600)
            # 打开首条详情
            try:
                page.get_by_role("button", name="详情").first.click(timeout=4000)
                page.wait_for_timeout(900)
            except Exception:
                try:
                    page.locator("tr").nth(1).dblclick(timeout=4000); page.wait_for_timeout(900)
                except Exception as e:
                    log.append(f"  --  open detail failed: {e}"); continue
            for idx, tab in enumerate(tabs):
                name = f"tab_{prefix}_{SUFFIX[TAB_KEY[tab]]}"
                if idx == 0:
                    # 默认基本信息已显示
                    shot(page, name)
                    continue
                try:
                    page.get_by_role("tab", name=tab).first.click(timeout=3500)
                    page.wait_for_timeout(900)
                    shot(page, name)
                except Exception as e:
                    log.append(f"  --  tab {tab} skip: {type(e).__name__}")
        browser.close()
    print("\n".join(log))
    print(f"\n=== {len(list(OUT.glob('tab_*.png')))} tab screenshots ===")


if __name__ == "__main__":
    sys.exit(main())
