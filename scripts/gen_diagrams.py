#!/usr/bin/env python3
"""生成 MetaProfile 三张系统图（架构/流程/部署）SVG，并用 Playwright Chromium 渲染为 PNG。"""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

FONT = "'Microsoft YaHei','SimHei',sans-serif"

# ── 通用样式 ──
def head(title, vb):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" font-family={FONT}>
<defs>
  <marker id="arr" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#475569"/></marker>
  <marker id="arrb" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#2563eb"/></marker>
</defs>
<rect width="100%" height="100%" fill="#ffffff"/>
<text x="480" y="34" text-anchor="middle" font-size="22" font-weight="700" fill="#0f172a">{title}</text>'''

FOOT = "</svg>"

def box(x, y, w, h, label, fill, sub=None, tc="#0f172a", fs=14):
    t = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="#334155" stroke-width="1.2"/>'
    cy = y + h/2 - (4 if sub else 0)
    t += f'<text x="{x+w/2}" y="{cy}" text-anchor="middle" font-size="{fs}" fill="{tc}" font-weight="600">{label}</text>'
    if sub:
        t += f'<text x="{x+w/2}" y="{cy+18}" text-anchor="middle" font-size="11" fill="#475569">{sub}</text>'
    return t

def layer(x, y, w, h, label, fill="#f1f5f9"):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
            f'stroke="#94a3b8" stroke-dasharray="6,4" stroke-width="1.2"/>'
            f'<text x="{x+12}" y="{y+20}" font-size="12" fill="#64748b" font-weight="700">{label}</text>')

def arrow(x1, y1, x2, y2, color="#475569", marker="arr", label=None, w=1.6):
    a = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}" marker-end="url(#{marker})"/>'
    if label:
        a += f'<text x="{(x1+x2)/2}" y="{(y1+y2)/2-6}" text-anchor="middle" font-size="11" fill="#334155">{label}</text>'
    return a


# ── 1. 系统架构图 ──
def architecture():
    s = head("MetaProfile 系统架构图（三层架构）", "0 0 1000 680")
    s += layer(40, 60, 920, 90, "前端展示层 (Frontend · React + Ant Design + G6)")
    s += box(80, 90, 150, 46, "Dashboard", "#dbeafe")
    s += box(245, 90, 150, 46, "四大画像", "#dbeafe")
    s += box(410, 90, 150, 46, "三大分析", "#dbeafe")
    s += box(575, 90, 150, 46, "数据源配置", "#dbeafe")
    s += box(740, 90, 180, 46, "nginx 反向代理", "#fef9c3", "/api-* → backend")
    s += arrow(500, 150, 500, 195, "#2563eb", "arrb", "REST /api/v1")
    s += layer(40, 200, 920, 95, "分析层 (Analysis · 消费画像 REST API)")
    s += box(80, 232, 280, 50, "前沿技术扫描监测 scan_monitor", "#dcfce7")
    s += box(380, 232, 260, 50, "新技术发现 new_tech_discovery", "#dcfce7")
    s += box(660, 232, 260, 50, "科技动态选题 topic_selection", "#dcfce7")
    s += arrow(500, 295, 500, 325, "#2563eb", "arrb")
    s += layer(40, 330, 920, 95, "画像层 (Profile · 四类实体业务封装)")
    s += box(80, 362, 210, 50, "技术画像 profile_tech", "#ede9fe")
    s += box(305, 362, 210, 50, "项目画像 profile_project", "#ede9fe")
    s += box(530, 362, 210, 50, "机构画像 profile_org", "#ede9fe")
    s += box(755, 362, 165, 50, "人物画像 profile_person", "#ede9fe")
    s += arrow(500, 425, 500, 455, "#2563eb", "arrb")
    s += layer(40, 460, 920, 95, "底座层 (Foundation · 重点目标对象模型)")
    s += box(60, 492, 150, 50, "采集 collectors", "#ffedd5", "8 数据源适配器")
    s += box(222, 492, 130, 50, "清洗 cleaners", "#ffedd5", "去重/归一/校验")
    s += box(364, 492, 120, 50, "NER ner", "#ffedd5", "BERT-CRF/UIE")
    s += box(496, 492, 130, 50, "抽取 extractors", "#ffedd5", "LLM Function")
    s += box(638, 492, 130, 50, "消歧/融合", "#ffedd5", "Embedding+LLM")
    s += box(780, 492, 140, 50, "存储 storage", "#ffedd5", "PG/ES/Neo4j")
    s += arrow(500, 575, 500, 605, "#2563eb", "arrb")
    s += layer(40, 590, 920, 80, "共享层 (Shared · config / db / llm / nlp / schemas / utils)")
    s += box(80, 615, 880, 40, "Pydantic 数据规范 · LiteLLM 网关 · BGE Embedding · Celery · structlog", "#e2e8f0", fs=12)
    return s + FOOT


# ── 2. 数据处理流程图 ──
def flow():
    s = head("MetaProfile 画像生成与查询流程图", "0 0 1000 620")
    steps = [
        ("数据采集", "专利/论文/项目/\n企业/政策/招标", "#dbeafe"),
        ("数据清洗", "去重 · 归一\n· 校验 · 评分", "#dbeafe"),
        ("实体识别", "BERT-CRF + UIE\n集成 NER", "#ede9fe"),
        ("属性抽取", "LLM Function\nCalling", "#ede9fe"),
        ("关系抽取", "规则 + LLM\n三元组", "#ede9fe"),
        ("消歧融合", "Embedding 召回\n+ LLM 精判", "#dcfce7"),
        ("三库入库", "PG · ES · Neo4j\n统一门面", "#dcfce7"),
        ("画像生成", "统计 · 完整度\n· RAG 补全", "#fef9c3"),
    ]
    x0, y0, w, h, gap = 70, 120, 180, 90, 50
    for i, (title, sub, fill) in enumerate(steps):
        row = i // 4
        col = i % 4
        x = x0 + col * (w + gap)
        y = y0 + row * 200
        s += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="#334155" stroke-width="1.3"/>'
        s += f'<text x="{x+w/2}" y="{y+28}" text-anchor="middle" font-size="15" font-weight="700" fill="#0f172a">{title}</text>'
        for j, line in enumerate(sub.split("\n")):
            s += f'<text x="{x+w/2}" y="{y+52+j*16}" text-anchor="middle" font-size="11" fill="#475569">{line}</text>'
        if col < 3:
            s += arrow(x + w, y + h/2, x + w + gap, y + h/2, "#2563eb", "arrb", w=2)
        elif row == 0:
            s += arrow(x + w/2, y + h, x + w/2, y + h + 110 - h, "#2563eb", "arrb", w=2)
    # 第二行反向（右→左）已在循环里用 col<3 处理；补第4→下 第8结束
    # 查询分支
    s += layer(60, 330, 880, 90, "查询与展示（画像层 REST API · 11 标准接口/类）")
    q = [("查询/搜索", "#fef9c3"), ("语义检索", "#fef9c3"), ("批量/统计", "#fef9c3"),
         ("关系图谱", "#fef9c3"), ("变更日志", "#fef9c3"), ("RAG 补全", "#fef9c3")]
    for i, (t, f) in enumerate(q):
        x = 90 + i * 140
        s += box(x, 360, 120, 46, t, f, fs=12)
    s += arrow(500, 415, 500, 450, "#2563eb", "arrb", "前端 G6 关系图 / Timeline / 表格")
    s += layer(60, 460, 880, 120, "存储")
    s += box(110, 490, 220, 70, "PostgreSQL", "#fee2e2", "结构化属性 + 子表（JSON）", fs=14)
    s += box(370, 490, 220, 70, "Elasticsearch", "#fee2e2", "全文检索 + kNN 向量", fs=14)
    s += box(630, 490, 250, 70, "Neo4j", "#fee2e2", "实体节点 + 关系图谱", fs=14)
    return s + FOOT


# ── 3. 部署图 ──
def deployment():
    s = head("MetaProfile 容器化部署图（Docker Compose）", "0 0 1000 640")
    # 用户
    s += box(410, 70, 180, 44, "用户浏览器", "#e0e7ff", "http://localhost:80")
    s += arrow(500, 114, 500, 150, "#2563eb", "arrb", "HTTP :80")
    s += layer(40, 155, 920, 80, "应用层（自建镜像 ×2）")
    s += box(90, 180, 360, 46, "frontend (nginx)", "#dbeafe", "metaprofile-frontend · :80")
    s += box(550, 180, 360, 46, "backend (uvicorn 复合 app)", "#bbf7d0", "metaprofile-backend · :8000 · 77 路由")
    s += arrow(450, 203, 550, 203, "#2563eb", "arrb", "反代 /api-*", w=2)
    s += arrow(500, 226, 500, 260, "#2563eb", "arrb")
    s += layer(40, 265, 920, 200, "基础设施层（不变 · 6 容器）")
    s += box(70, 305, 200, 60, "postgres:15", "#fef3c7", ":5432 · 业务库", fs=14)
    s += box(290, 305, 200, 60, "elasticsearch:8", "#fef3c7", ":9200 · 全文+向量", fs=14)
    s += box(510, 305, 200, 60, "neo4j:5.16", "#fef3c7", ":7687 · 关系图谱", fs=14)
    s += box(730, 305, 190, 60, "redis:7", "#fef3c7", ":6379 · 缓存", fs=14)
    s += box(180, 385, 280, 60, "rabbitmq:3.12", "#fef3c7", ":5672 · Celery 队列", fs=14)
    s += box(540, 385, 280, 60, "litellm (LLM 代理)", "#fef3c7", ":4000 → Qwen/BGE", fs=14)
    # 一次性 job
    s += layer(40, 480, 920, 120, "一次性 Job（复用 backend 镜像）")
    s += box(120, 510, 340, 60, "migrate", "#e2e8f0", "alembic upgrade head · 建表", fs=14)
    s += box(540, 510, 340, 60, "seed", "#e2e8f0", "gen_mock_data.py · 100×4 + 图谱", fs=14)
    s += arrow(290, 510, 290, 366, "#94a3b8", "arr", None, 1.2)
    s += arrow(710, 510, 710, 366, "#94a3b8", "arr", None, 1.2)
    return s + FOOT


def render(svg_text, name):
    import re
    svg_path = OUT / f"{name}.svg"
    png_path = OUT / f"{name}.png"
    svg_path.write_text(svg_text, encoding="utf-8")
    # 从 viewBox 取宽高，显式设到 svg 上，避免页面 0 高
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg_text)
    w, h = (m.group(1), m.group(2)) if m else ("1000", "700")
    sized = svg_text.replace("<svg ", f'<svg width="{w}" height="{h}" ', 1)
    html = (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<style>*{{margin:0;padding:0}}body{{background:#fff}}</style></head>'
            f'<body>{sized}</body></html>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": int(float(w)), "height": int(float(h))},
                        device_scale_factor=2)
        pg.set_content(html)
        pg.wait_for_timeout(200)
        pg.locator("svg").screenshot(path=str(png_path))
        b.close()
    print(f"  {name}: {png_path}  ({w}x{h})")


if __name__ == "__main__":
    print("生成图表到", OUT)
    render(architecture(), "architecture")
    render(flow(), "flow")
    render(deployment(), "deployment")
    print("done")
