#!/usr/bin/env python3
"""
模拟数据生成脚本（确定性 + 可重跑）。

生成 ~100 个技术 / 100 个人 / 100 个组织 / 100 个项目，属性齐全，
并构建它们之间的关系图谱。

存储策略（与 app 读取路径一致）：
- PostgreSQL：写入四类画像的 typed ORM 表（tech_profile / project_profile /
  org_profile / person_profile 及其子表）+ entity_change_log。
  —— 这是 profile 层 REST API 真正读取的数据源。
- Neo4j：写入实体节点 + 关系（隶属/承研/管理/涉及/贡献者/合作…）。
  —— relation 图谱 / 路径查询读取这里。
- Elasticsearch：写入实体文档（不含向量）。
  —— semantic search 读取这里（向量需 embedding 服务）。

可重跑保证：
- 实体 id 用 stable_id_from_attrs（基于名称哈希），每次相同。
- mock id 形如 TECH_S_<hash> / PROJECT_S_<hash> / ORG_S_<hash> / PERSON_S_<hash>。
- 同时导出 deploy/mock_data.sql（PG）与 deploy/mock_data.cypher（Neo4j），
  可脱离本脚本直接 `psql -f` / neo4j 导入，反复重建数据。

用法：
    py -3.12 scripts/gen_mock_data.py            # 实时写三库 + 导出 SQL/Cypher
    py -3.12 scripts/gen_mock_data.py --sql-only  # 仅生成 SQL/Cypher 文件，不连库
    py -3.12 scripts/gen_mock_data.py --count 50  # 每类实体数量（默认 100）
    py -3.12 scripts/gen_mock_data.py --no-neo4j --no-es   # 跳过 Neo4j/ES
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ───────────────────────── CLI：先解析再设 env，最后才 import metaprofile ──

DEFAULTS = {
    "POSTGRES_DSN": "postgresql+asyncpg://metaprofile:metaprofile@localhost:5432/metaprofile",
    "ES_HOSTS": '["http://localhost:9200"]',
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "password",
    "REDIS_DSN": "redis://localhost:6379/0",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MetaProfile 模拟数据生成")
    p.add_argument("--count", type=int, default=100, help="每类实体数量（默认 100）")
    p.add_argument("--seed", type=int, default=20260615, help="随机种子")
    p.add_argument("--sql-only", action="store_true", help="只导出 SQL/Cypher，不连库")
    p.add_argument("--no-pg", action="store_true", help="跳过 PostgreSQL 实时写入")
    p.add_argument("--no-neo4j", action="store_true", help="跳过 Neo4j 实时写入")
    p.add_argument("--no-es", action="store_true", help="跳过 Elasticsearch 实时写入")
    p.add_argument(
        "--postgres-dsn", default=DEFAULTS["POSTGRES_DSN"], help="PG DSN"
    )
    p.add_argument("--neo4j-uri", default=DEFAULTS["NEO4J_URI"])
    p.add_argument("--neo4j-user", default=DEFAULTS["NEO4J_USER"])
    p.add_argument("--neo4j-password", default=DEFAULTS["NEO4J_PASSWORD"])
    return p.parse_args()


ARGS = parse_args()
# 在 import metaprofile.* 之前注入连接参数
os.environ.setdefault("POSTGRES_DSN", ARGS.postgres_dsn)
os.environ.setdefault("ES_HOSTS", '["http://localhost:9200"]')
os.environ.setdefault("NEO4J_URI", ARGS.neo4j_uri)
os.environ.setdefault("NEO4J_USER", ARGS.neo4j_user)
os.environ.setdefault("NEO4J_PASSWORD", ARGS.neo4j_password)
os.environ.setdefault("REDIS_DSN", DEFAULTS["REDIS_DSN"])

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
NOW_STR = NOW.isoformat()

# ───────────────────────── 数据池 ─────────────────────────────────────────

TECH_DOMAINS = [
    "人工智能", "大模型", "量子计算", "半导体", "集成电路", "生物医药", "基因编辑",
    "新能源", "氢能", "储能", "航空航天", "卫星互联网", "新材料", "增材制造",
    "机器人", "脑机接口", "5G通信", "6G通信", "光电技术", "深海装备", "网络安全",
    "自动驾驶", "无人机", "先进算力", "碳捕集",
]
TECH_STATUS = ["概念论证", "实验室阶段", "中试阶段", "工程化应用", "规模化部署"]
TECH_TREND = ["快速上升", "稳步上升", "平稳", "波动", "下降"]
COUNTRIES = ["中国", "美国", "日本", "德国", "韩国", "英国", "法国", "俄罗斯", "以色列", "新加坡"]
ORG_NATURES = ["抽象机构", "实体机构"]
ORG_TYPES = ["管理机构", "科研机构", "高校", "企业", "咨询机构", "试验鉴定机构", "其他"]
PERSON_DEGREES = ["博士", "硕士", "本科"]
PERSON_CATEGORIES = ["管理", "研究", "其他"]
GENDERS = ["男", "女"]
PROJECT_STATUS = ["进行中", "结束", "成果已转化"]
REVIEW_TYPES = ["正面信息", "负面信息", "其他"]
ACADEMIC_FORMS = ["论文", "专著", "专利", "汇报文稿"]
AUTHOR_RANKS = ["独著", "第一作者", "第二作者", "第三作者", "其他"]
BUDGET_ACTIVITIES = [
    "基础技术研究BA-1", "应用技术研究BA-2", "先期技术开发BA-3",
    "先期部件研制与样机开发BA-4", "系统开发与演示验证BA-5",
    "软件研究/开发/测试和评估试点BA-8",
]
POSITIONS = ["研究员", "教授", "总工程师", "首席科学家", "副院长", "主任", "高级工程师", "副教授"]

TECH_PREFIX = [
    "新型", "高性能", "低功耗", "智能化", "分布式", "自主可控", "高可靠", "小型化",
    "一体化", "柔性",
]
TECH_CORE = [
    "神经网络芯片", "量子纠错码", "碳化硅功率器件", "mRNA疫苗", "固态电池",
    "可重复使用火箭", "钙钛矿太阳能电池", "金属3D打印", "仿生机械臂", "光量子计算",
    "氢燃料电池电堆", "毫米波雷达", "基因剪刀", "类脑计算架构", "卫星星座组网",
    "碳纳米管", "神经形态芯片", "深海潜水器", "自动驾驶域控制器", "太赫兹通信",
]
TECH_SUFFIX = ["技术", "系统", "工艺", "方法", "平台", "装置", "解决方案"]

ORG_PREFIXES_CN = ["华", "中", "国", "新", "东方", "北方", "南方", "远", "航天", "中科"]
ORG_CORE_CN = [
    "芯创", "量子", "智算", "生医", "氢动", "航宇", "光电", "新材", "深海", "天网",
    "算力", "脑科学", "基因", "储能", "微纳", "聚变", "信息", "先进", "前沿", "未来",
]
ORG_SUFFIXES_CN = ["科技", "研究院", "研究所", "实验室", "集团", "股份", "高科", "工程技术中心"]

PERSON_SURNAMES = list("王李张刘陈杨黄赵周吴徐孙马朱胡郭何高林郑谢罗梁宋唐许韩冯邓曹彭")
PERSON_GIVEN = [
    "伟", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "霞", "平",
    "刚", "桂英", "建华", "志强", "晓东", "海燕", "文博", "俊杰", "宇航", "雪松", "瑞",
    "昊", "婷", "宁", "峰", "斌",
]

PROJECT_PREFIX = ["重点", "重大", "前沿", "基础", "应用", "攻关", "先导", "专项"]
PROJECT_CORE = ["研发", "突破", "工程", "产业化", "验证", "示范", "攻关", "研制"]
PROJECT_SUFFIX = ["计划", "项目", "工程", "专项", "课题", "任务"]


def gen_name(rng: random.Random) -> tuple[str, str]:
    surname = rng.choice(PERSON_SURNAMES)
    given = "".join(rng.sample(PERSON_GIVEN, rng.choice([1, 2])))
    cn = surname + given
    en = "Expert_" + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6)).capitalize()
    return cn, en


def gen_tech_name(rng: random.Random, idx: int) -> tuple[str, str]:
    cn = f"{rng.choice(TECH_PREFIX)}{rng.choice(TECH_CORE)}{rng.choice(TECH_SUFFIX)}"
    en = f"Tech-{idx:03d} " + rng.choice(TECH_CORE).replace(" ", "")
    return cn, en.strip()


def gen_org_name(rng: random.Random, idx: int) -> tuple[str, str]:
    cn = f"{rng.choice(ORG_PREFIXES_CN)}{rng.choice(ORG_CORE_CN)}{rng.choice(ORG_SUFFIXES_CN)}"
    en = f"Org-{idx:03d}"
    return cn, en


def gen_project_name(rng: random.Random, idx: int) -> tuple[str, str]:
    cn = f"{rng.choice(PROJECT_PREFIX)}{rng.choice(TECH_CORE)}{rng.choice(PROJECT_SUFFIX)}"
    en = f"Project-{idx:03d}"
    return cn, en


def daterange(rng: random.Random, start_year: int, end_year: int):
    y = rng.randint(start_year, end_year)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    return date(y, m, d)


def psample(rng: random.Random, pop: list, k: int) -> list:
    """带人口上限 clamp 的随机抽样（防止 k>len(pop)）。"""
    return rng.sample(pop, min(k, len(pop)))


# ───────────────────────── 数据集构造 ─────────────────────────────────────

@dataclass
class Dataset:
    techs: list[dict] = field(default_factory=list)
    orgs: list[dict] = field(default_factory=list)
    persons: list[dict] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    # 分析层
    frontier_tech: list[dict] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)
    signals: list[dict] = field(default_factory=list)
    signal_edges: list[dict] = field(default_factory=list)
    topics: list[dict] = field(default_factory=list)


def build_dataset(n: int, seed: int) -> Dataset:
    rng = random.Random(seed)
    ds = Dataset()

    # ── 组织（先建，后续实体引用） ──
    for i in range(n):
        cn, en = gen_org_name(rng, i)
        oid = stable_org_id(cn, i)
        founded = daterange(rng, 1950, 2018)
        nature = rng.choice(ORG_NATURES)
        domains = rng.sample(TECH_DOMAINS, rng.randint(2, 5))
        org: dict[str, Any] = {
            "org_id": oid,
            "name_cn": cn,
            "name_en": en,
            "name_other": [],
            "country": rng.choice(COUNTRIES),
            "founded_date": founded,
            "dissolved_date": None,
            "operating_years": 2026 - founded.year,
            "website": f"www.{en.lower()}.example.com",
            "summary": f"{cn}是聚焦{('、'.join(domains[:3]))}等领域的{nature}，"
            f"致力于前沿技术研发与成果转化。",
            "org_types": rng.sample(ORG_TYPES, rng.randint(1, 3)),
            "nature": nature,
            "function": rng.choice(
                ["基础研究", "应用研究", "技术开发", "成果转化", "人才培养", "战略咨询"]
            ),
            "scale": rng.choice([200, 500, 1000, 3000, 8000, 15000]),
            "tech_domains": domains,
            "predecessor_names": [],
            "departments": f"{cn}下设基础研究部、应用工程部、国际合作部",
            "strategic_plans": [f"{d}五年发展规划" for d in ["2021-2025", "2026-2030"]],
            "evaluation_report": f"{cn}在{rng.choice(domains)}领域处于国内领先水平。",
            "new_key_projects": rng.sample(TECH_CORE, rng.randint(1, 3)),
            "remark": "",
            "confidence": round(rng.uniform(0.7, 0.99), 3),
            "completeness": round(rng.uniform(0.55, 0.95), 3),
            "children": {
                "org_history": [
                    {"change_date": daterange(rng, 2010, 2024),
                     "change_description": desc}
                    for desc in [f"成立{rng.choice(domains)}研究中心", "完成股份制改革",
                                 "获批国家重点实验室"]
                ],
                "org_award": [
                    {"name": rng.choice(["国家科技进步奖", "省部级一等奖", "行业金奖"]),
                     "award_type": rng.choice(["科技", "工程", "创新"]),
                     "level": rng.choice(["国家级", "省部级", "行业级"]),
                     "award_date": daterange(rng, 2015, 2024),
                     "reason": f"在{rng.choice(domains)}取得突破", "description": ""}
                    for _ in range(rng.randint(1, 3))
                ],
                "org_output": [
                    {"name": f"{rng.choice(domains)}{rng.choice(['关键技术','系统','标准'])}",
                     "form": rng.choice(["论文", "专利", "标准", "软件著作权"]),
                     "author": cn, "publish_date": daterange(rng, 2018, 2024),
                     "attachment": ""}
                    for _ in range(rng.randint(2, 4))
                ],
                "org_team": [{
                    "team_size": rng.choice([200, 500, 1000]),
                    "talent_type": rng.choice(["研发团队", "工程团队", "战略科学家团队"]),
                    "top_talents": [f"{gen_name(rng)[0]}院士" for _ in range(rng.randint(1, 2))],
                    "award_winners": [gen_name(rng)[0] for _ in range(rng.randint(1, 3))],
                }],
                "org_facility": [
                    {"name": f"{rng.choice(domains)}实验平台",
                     "purpose": f"开展{rng.choice(domains)}关键实验",
                     "experiment_status": rng.choice(["运行中", "在建", "调试"]),
                     "launch_date": daterange(rng, 2018, 2024),
                     "construction_cost_wan_usd": rng.choice([500, 2000, 8000, 15000])}
                    for _ in range(rng.randint(1, 2))
                ],
            },
        }
        ds.orgs.append(org)

    org_ids = [o["org_id"] for o in ds.orgs]
    org_by_id = {o["org_id"]: o for o in ds.orgs}

    # ── 人员 ──
    for i in range(n):
        cn, en = gen_name(rng)
        pid = stable_person_id(cn, i)
        gender = rng.choice(GENDERS)
        birth = daterange(rng, 1955, 1995)
        employer = rng.choice(ds.orgs)
        domains = rng.sample(TECH_DOMAINS, rng.randint(1, 4))
        person: dict[str, Any] = {
            "person_id": pid,
            "name_cn": cn,
            "name_en": en,
            "gender": gender,
            "avatar": [],
            "nationality": "中国",
            "summary": f"{cn}，{rng.choice(PERSON_CATEGORIES)}，"
            f"主要从事{('、'.join(domains[:2]))}研究，"
            f"现任{employer['name_cn']}{rng.choice(POSITIONS)}。",
            "birth_date": birth,
            "age": 2026 - birth.year,
            "birthplace": rng.choice(["北京", "上海", "南京", "西安", "成都", "武汉", "哈尔滨"]),
            "ethnicity": "汉族",
            "current_residence": rng.choice(["北京", "上海", "深圳", "杭州"]),
            "current_org": employer["name_cn"],
            "current_enterprise": employer["name_cn"] if "企业" in employer["org_types"] else None,
            "current_military_unit": None,
            "current_position": [rng.choice(POSITIONS)],
            "highest_degree": rng.choice(PERSON_DEGREES),
            "person_category": rng.choice(PERSON_CATEGORIES),
            "professional_domains": domains,
            "professional_skills": rng.sample(
                ["系统架构", "算法设计", "实验验证", "工程化", "项目管理", "数据分析"], rng.randint(2, 4)
            ),
            "social_media": "",
            "personality_traits": rng.sample(["严谨", "务实", "创新", "协作", "坚韧"], rng.randint(1, 3)),
            "hobbies": rng.sample(["阅读", "运动", "音乐", "旅行"], rng.randint(1, 2)),
            "management_philosophy": ["产学研结合", "以问题为导向"],
            "remark": [],
            "confidence": round(rng.uniform(0.7, 0.98), 3),
            "completeness": round(rng.uniform(0.55, 0.95), 3),
            "_employer_org_id": employer["org_id"],
            "children": {
                "person_education": [{
                    "start_date": daterange(rng, 1990, 2010),
                    "degree_date": daterange(rng, 1998, 2018),
                    "degree": rng.choice(PERSON_DEGREES),
                    "school": rng.choice(["清华大学", "北京大学", "浙江大学", "上海交通大学",
                                          "中国科学技术大学", "哈尔滨工业大学"]),
                    "major": rng.choice(domains[:1] + TECH_DOMAINS[:5]),
                }],
                "person_career": [{
                    "start_date": daterange(rng, 2005, 2020),
                    "end_date": None,
                    "org": employer["name_cn"],
                    "enterprise": employer["name_cn"] if "企业" in employer["org_types"] else None,
                    "military_unit": None,
                    "position": rng.choice(POSITIONS),
                }],
                "person_award": [
                    {"description": f"{y}年获{rng.choice(['国家自然科学奖','省部级奖励','学会优秀论文'])}"}
                    for y in [rng.randint(2015, 2024)]
                ],
                "person_academic_output": [
                    {"name": f"关于{rng.choice(domains)}的{rng.choice(['研究','综述','方法'])}",
                     "form": rng.choice(ACADEMIC_FORMS),
                     "publish_date": daterange(rng, 2018, 2024),
                     "rank": rng.choice(AUTHOR_RANKS),
                     "tech_domain": rng.choice(domains),
                     "collaborators": [gen_name(rng)[0] for _ in range(rng.randint(1, 3))],
                     "citations": rng.randint(5, 800),
                     "is_representative": True}
                    for _ in range(rng.randint(2, 4))
                ],
                "person_focus": [
                    {"focus_type": "tech",
                     "content": [f"{rng.choice(domains)}前沿方向"],
                     "consistency_with_policy": "符合国家科技创新规划",
                     "potential_impact": ["推动产业升级", "形成自主知识产权"]},
                ],
            },
        }
        ds.persons.append(person)
        # ORG 雇佣 PERSON（org → person）
        ds.relations.append(rel(employer["org_id"], "ORG", employer["name_cn"],
                                pid, "PERSON", "ORG_EMPLOY", 0.95))
        # PERSON 隶属 ORG（person → org）
        ds.relations.append(rel(pid, "PERSON", cn,
                                employer["org_id"], "ORG", "PERSON_AFFILIATED_ORG", 0.95))

    person_ids = [p["person_id"] for p in ds.persons]

    # ── 技术 ──
    for i in range(n):
        cn, en = gen_tech_name(rng, i)
        tid = stable_tech_id(cn, i)
        domain = rng.choice(TECH_DOMAINS)
        domains = list({domain, rng.choice(TECH_DOMAINS)})
        tech: dict[str, Any] = {
            "tech_id": tid,
            "tech_name_cn": cn,
            "tech_name_en": en,
            "tech_name_other": None,
            "tech_domain": domains,
            "invention_date": daterange(rng, 2000, 2020),
            "application_date": daterange(rng, 2018, 2025),
            "tech_summary": f"{cn}是{domain}领域的关键技术，"
            f"具有{rng.choice(['高效率','低成本','高可靠性'])}等优势，应用前景广阔。",
            "dev_goal": f"突破{domain}核心技术瓶颈，实现自主可控。",
            "project_layout": [f"{domain}基础理论", f"{domain}工程化"],
            "key_points": [f"{domain}关键工艺", f"{domain}系统集成"],
            "transformation_status": rng.choice(["已转化", "转化中", "待转化"]),
            "basic_research_status": "基础理论已建立",
            "autonomy_capability": "具备完全自主知识产权",
            "industrial_capability": "形成完整产业链",
            "tech_advantages": f"相比同类技术，{cn}在性能与成本上优势明显。",
            "current_status": rng.choice(TECH_STATUS),
            "trend": rng.choice(TECH_TREND),
            "remark": "",
            "confidence": round(rng.uniform(0.7, 0.98), 3),
            "completeness": round(rng.uniform(0.55, 0.95), 3),
            "children": {
                "tech_dev_milestone": [
                    {"milestone_date": daterange(rng, 2010, 2024),
                     "milestone_name": ev,
                     "contributor_keywords": [rng.choice(ds.orgs)["name_cn"]],
                     "milestone_content": f"{ev}：实现{domain}关键突破。"}
                    for ev in ["概念提出", "实验室验证", "工程样机", "中试成功", "产业化"]
                ],
                "tech_funding": [
                    {"amount": float(rng.choice([500, 1000, 3000, 8000, 15000])),
                     "source": rng.choice(["国家自然科学基金", "国家重点研发计划", "企业自筹", "地方专项"])}
                    for _ in range(rng.randint(1, 3))
                ],
                "tech_academic_output": [
                    {"name": f"{cn}相关研究",
                     "publish_date": daterange(rng, 2018, 2024),
                     "subject_keywords": [rng.choice(ds.orgs)["name_cn"]],
                     "image": ""}
                    for _ in range(rng.randint(1, 3))
                ],
                "tech_experiment": [{
                    "content": f"{cn}原理验证实验",
                    "experiment_date": daterange(rng, 2020, 2024),
                    "result": "实验数据达到预期指标",
                    "subject_keywords": [domain],
                    "image": "",
                }],
            },
        }
        ds.techs.append(tech)
        # 技术贡献者（机构 + 人员）
        owner_org = rng.choice(ds.orgs)
        ds.relations.append(rel(tid, "TECH", cn, owner_org["org_id"], "ORG",
                                "TECH_CONTRIBUTOR", 0.9))  # 注意方向：tech→? 见下
        contrib_person = rng.choice(ds.persons)
        ds.relations.append(rel(tid, "TECH", cn, contrib_person["person_id"], "PERSON",
                                "TECH_CONTRIBUTOR", 0.85))

    tech_ids = [t["tech_id"] for t in ds.techs]

    # ── 项目 ──
    base_no = 10000
    for i in range(n):
        cn, en = gen_project_name(rng, i)
        pid = stable_project_id(cn, i)
        domain = rng.choice(TECH_DOMAINS)
        domains = list({domain, rng.choice(TECH_DOMAINS)})
        main_org = rng.choice(ds.orgs)
        undertake_orgs = psample(rng, ds.orgs, rng.randint(1, 2))
        managers = psample(rng, ds.persons, rng.randint(1, 2))
        researchers = psample(rng, ds.persons, rng.randint(2, 4))
        involved_techs = psample(rng, ds.techs, rng.randint(1, 3))
        start = daterange(rng, 2018, 2024)
        project: dict[str, Any] = {
            "project_id": pid,
            "name_cn": [cn],
            "name_en": [en],
            "name_other": [],
            "tech_domain": domains,
            "sub_tech_domain": rng.sample(TECH_DOMAINS, rng.randint(1, 2)),
            "start_date": start,
            "cancel_date": None,
            "finish_date": start if rng.random() < 0.2 else None,
            "status": [rng.choice(PROJECT_STATUS)],
            "budget_activities": [rng.choice(BUDGET_ACTIVITIES)],
            "project_no": base_no + i,
            "main_orgs": [main_org["name_cn"]],
            "undertaking_orgs": [o["name_cn"] for o in undertake_orgs],
            "undertaking_enterprises": [o["name_cn"] for o in undertake_orgs if o["nature"] == "企业"],
            "managers": [p["name_cn"] for p in managers],
            "researchers": [p["name_cn"] for p in researchers],
            "background": [f"针对{domain}领域关键需求立项"],
            "research_goal": f"突破{domain}关键技术，形成自主可控能力。",
            "research_content": [f"{domain}理论研究", f"{domain}工程化", f"{domain}应用验证"],
            "keywords": domains,
            "progress": [f"{start.year}年完成方案论证", f"{start.year+1}年进入工程研制"],
            "application_prospect": "成果可应用于相关产业领域。",
            "key_dates": [daterange(rng, 2020, 2024) for _ in range(rng.randint(1, 3))],
            "total_budget_million_usd": float(rng.choice([5.0, 20.0, 50.0, 120.0, 300.0])),
            "invested_million_usd": float(rng.choice([2.0, 10.0, 30.0, 80.0])),
            "parent_package_name": rng.choice(["重大专项", "重点研发", None]),
            "previous_phase_name": None,
            "confidence": round(rng.uniform(0.7, 0.97), 3),
            "completeness": round(rng.uniform(0.55, 0.95), 3),
            "children": {
                "project_history": [
                    {"change_date": daterange(rng, 2019, 2024),
                     "change_description": ev}
                    for ev in ["立项批复", "通过中期评审", "转入工程阶段"]
                ],
                "project_budget": [
                    {"budget_date": daterange(rng, 2020, 2024),
                     "amount": float(rng.choice([50.0, 200.0, 800.0, 2000.0]))}
                    for _ in range(rng.randint(1, 3))
                ],
                "project_output": [
                    {"name_history": f"{domain}{rng.choice(['关键技术','成果','样机'])}",
                     "formed_at": daterange(rng, 2021, 2024),
                     "tech_domains": domains,
                     "owner_orgs": [main_org["name_cn"]],
                     "related_projects": [], "attachments": []}
                    for _ in range(rng.randint(1, 3))
                ],
            },
        }
        ds.projects.append(project)
        # 项目关系
        ds.relations.append(rel(pid, "PROJECT", cn, main_org["org_id"], "ORG",
                                "PROJECT_MAIN_ORG", 0.95))
        for o in undertake_orgs:
            ds.relations.append(rel(pid, "PROJECT", cn, o["org_id"], "ORG",
                                    "PROJECT_UNDERTAKE_ORG", 0.9))
        for p in managers:
            ds.relations.append(rel(pid, "PROJECT", cn, p["person_id"], "PERSON",
                                    "PROJECT_MANAGER", 0.92))
        for p in researchers:
            ds.relations.append(rel(pid, "PROJECT", cn, p["person_id"], "PERSON",
                                    "PROJECT_RESEARCHER", 0.85))
        for t in involved_techs:
            ds.relations.append(rel(pid, "PROJECT", cn, t["tech_id"], "TECH",
                                    "PROJECT_INVOLVE_TECH", 0.8))

    # ── 补充：机构间关系（父子/合作）、人员合作、项目阶段链 ──
    for _ in range(n // 3):
        parent, child = rng.sample(ds.orgs, 2)
        ds.relations.append(rel(parent["org_id"], "ORG", parent["name_cn"],
                                child["org_id"], "ORG", "ORG_PARENT", 0.9))
    for _ in range(n // 2):
        a, b = rng.sample(ds.orgs, 2)
        ds.relations.append(rel(a["org_id"], "ORG", a["name_cn"],
                                b["org_id"], "ORG", "ORG_COOPERATE", 0.8))
    for _ in range(n // 2):
        a, b = rng.sample(ds.persons, 2)
        ds.relations.append(rel(a["person_id"], "PERSON", a["name_cn"],
                                b["person_id"], "PERSON", "PERSON_COOPERATE", 0.75))
    for i in range(0, len(ds.projects) - 1, 4):
        a, b = ds.projects[i], ds.projects[i + 1]
        ds.relations.append(rel(a["project_id"], "PROJECT", a["name_cn"][0],
                                b["project_id"], "PROJECT", "PROJECT_NEXT_PHASE", 0.85))

    build_analysis(ds, rng)
    return ds


def build_analysis(ds: Dataset, rng: random.Random) -> None:
    """生成分析层数据（frontier_tech / scan_alert / weak_signal / topic_candidate）。"""
    pf, pt = date(2025, 7, 1), date(2026, 6, 1)

    # ── frontier_tech（取前 18 个技术，按融合分排序） ──
    sample_techs = ds.techs[:18]
    for rank, t in enumerate(sample_techs):
        burst = round(rng.uniform(0.4, 0.98), 3)
        patent = round(rng.uniform(0.3, 0.95), 3)
        citation = round(rng.uniform(0.3, 0.9), 3)
        invest = round(rng.uniform(0.2, 0.85), 3)
        policy = round(rng.uniform(0.2, 0.8), 3)
        fusion = round((burst + patent + citation + invest + policy) / 5, 3)
        ft = {
            "id": None, "scan_task_id": f"scan_mock_{rank:03d}",
            "tech_id": t["tech_id"], "tech_name": t["tech_name_cn"],
            "tech_domain": t["tech_domain"], "period_from": pf, "period_to": pt,
            "burst_score": burst, "patent_score": patent, "citation_score": citation,
            "invest_score": invest, "policy_score": policy, "fusion_score": fusion,
            "llm_validated": rank < 10, "llm_verdict": rng.choice(["是", "否", "待定"]) if rank < 10 else None,
            "llm_evidence": "多源信号交叉验证" if rank < 10 else None,
            "trl_level": rng.randint(2, 8), "status": "validated" if rank < 10 else "pending",
            "created_at": NOW, "updated_at": NOW,
        }
        ds.frontier_tech.append(ft)
        # 每个前沿技术配 0-1 条告警
        if rng.random() < 0.6:
            ds.alerts.append({
                "id": None, "frontier_tech_id": rank + 1,
                "tech_name": t["tech_name_cn"],
                "alert_type": rng.choice(["burst", "trl_upgrade", "org_layout"]),
                "severity": rng.choice(["info", "warn", "critical"]),
                "message": rng.choice([
                    f"{t['tech_name_cn']} 关键词突现，关注度显著上升",
                    f"{t['tech_name_cn']} TRL 等级提升",
                    f"关键机构在 {t['tech_name_cn']} 领域布局变化",
                ]),
                "fired_at": NOW, "is_read": rng.random() < 0.3,
                "created_at": NOW, "updated_at": NOW,
            })

    # ── weak_signal（新技术发现）+ 关联网络边 ──
    for i in range(18):
        kw = [rng.choice(TECH_DOMAINS) for _ in range(rng.randint(1, 3))]
        tid = rng.choice(ds.techs)["tech_id"]
        oid = rng.choice(ds.orgs)["org_id"]
        pid = rng.choice(ds.persons)["person_id"]
        sid = f"SIG_{i:03d}_{rng.randint(1000, 9999)}"
        ds.signals.append({
            "id": None, "signal_id": sid,
            "keywords": kw, "related_tech_ids": [tid],
            "related_org_ids": [oid],
            "related_person_ids": [pid],
            "evidence_doc_ids": [],
            "strength": round(rng.uniform(0.3, 0.95), 3),
            "novelty": round(rng.uniform(0.3, 0.95), 3),
            "coherence": round(rng.uniform(0.3, 0.9), 3),
            "diversity": round(rng.uniform(0.2, 0.85), 3),
            "velocity": round(rng.uniform(0.2, 0.9), 3),
            "period_from": pf, "period_to": pt, "domain": rng.choice(TECH_DOMAINS),
            "status": "active", "created_at": NOW, "updated_at": NOW,
        })
        # 信号关联网络边（共现/引用/资助）
        for src, st, tgt, tt, et in [
            (tid, "tech", oid, "org", "co_occurrence"),
            (oid, "org", pid, "person", "funding"),
            (tid, "tech", pid, "person", "citation"),
        ]:
            ds.signal_edges.append({
                "id": None, "signal_id": sid, "source_id": src, "source_type": st,
                "target_id": tgt, "target_type": tt, "edge_type": et,
                "weight": round(rng.uniform(0.3, 0.95), 3),
                "created_at": NOW, "updated_at": NOW,
            })

    # ── topic_candidate（选题） ──
    for i in range(12):
        domain = rng.choice(TECH_DOMAINS)
        ds.topics.append({
            "id": None, "topic_id": f"TOPIC_{i:03d}_{rng.randint(1000,9999)}",
            "title": f"{domain}{rng.choice(['前沿进展','技术突破','产业动态','发展趋势'])}选题",
            "summary": f"围绕{domain}领域近期突现信号与机构布局变化，建议开展情报选题研究。",
            "period": rng.choice(["2026Q1", "2026Q2", "2026Q3"]),
            "related_tech_ids": [rng.choice(ds.techs)["tech_id"]],
            "related_org_ids": [rng.choice(ds.orgs)["org_id"]],
            "related_project_ids": [rng.choice(ds.projects)["project_id"]],
            "related_policy_refs": [],
            "score_hot": round(rng.uniform(0.4, 0.95), 3),
            "score_policy": round(rng.uniform(0.3, 0.9), 3),
            "score_impact": round(rng.uniform(0.3, 0.9), 3),
            "score_dedup": round(rng.uniform(0.5, 0.95), 3),
            "score_llm_gen": round(rng.uniform(0.3, 0.9), 3),
            "review_novelty": round(rng.uniform(0.4, 0.95), 3),
            "review_importance": round(rng.uniform(0.4, 0.9), 3),
            "review_feasibility": round(rng.uniform(0.4, 0.9), 3),
            "review_expression": round(rng.uniform(0.4, 0.9), 3),
            "review_evidence": None,
            "final_score": round(rng.uniform(0.5, 0.95), 3),
            "status": rng.choice(["pending", "accepted", "rejected", "revised"]),
            "created_at": NOW, "updated_at": NOW,
        })


# ───────────────────────── id / relation 辅助 ─────────────────────────────

def stable_tech_id(name: str, idx: int) -> str:
    import hashlib
    return "TECH_S_" + hashlib.sha256(f"TECH::{name}::{idx}".encode()).hexdigest()[:16]


def stable_org_id(name: str, idx: int) -> str:
    import hashlib
    return "ORG_S_" + hashlib.sha256(f"ORG::{name}::{idx}".encode()).hexdigest()[:16]


def stable_person_id(name: str, idx: int) -> str:
    import hashlib
    return "PERSON_S_" + hashlib.sha256(f"PERSON::{name}::{idx}".encode()).hexdigest()[:16]


def stable_project_id(name: str, idx: int) -> str:
    import hashlib
    return "PROJECT_S_" + hashlib.sha256(f"PROJECT::{name}::{idx}".encode()).hexdigest()[:16]


def rel(subj_id: str, subj_type: str, subj_name: str | None,
        obj_id: str, obj_type: str, rel_type: str, conf: float) -> dict:
    """构造关系三元组（统一位置参数）。"""
    return {
        "subject_id": subj_id,
        "subject_type": subj_type,
        "subject_name": subj_name,
        "object_id": obj_id,
        "object_type": obj_type,
        "relation": rel_type,
        "confidence": conf,
        "method": "rule",
        "evidence": "",
        "source_doc_id": "mock_seed",
    }


# ───────────────────────── SQL / Cypher 导出 ──────────────────────────────

# 每张表的列（顺序即 SQL 列顺序）
TABLES: dict[str, list[str]] = {
    "tech_profile": ["tech_id", "tech_name_cn", "tech_name_en", "tech_name_other",
                     "tech_domain", "invention_date", "application_date", "tech_summary",
                     "dev_goal", "project_layout", "key_points", "transformation_status",
                     "basic_research_status", "autonomy_capability", "industrial_capability",
                     "tech_advantages", "current_status", "trend", "remark",
                     "confidence", "completeness", "created_at", "updated_at"],
    "tech_dev_milestone": ["id", "tech_id", "milestone_date", "milestone_name",
                           "contributor_keywords", "milestone_content", "created_at", "updated_at"],
    "tech_review_impact": ["id", "tech_id", "review_date", "review_org", "review_person",
                           "review_content", "review_type", "created_at", "updated_at"],
    "tech_funding": ["id", "tech_id", "amount", "source", "created_at", "updated_at"],
    "tech_academic_output": ["id", "tech_id", "name", "publish_date", "subject_keywords",
                             "image", "created_at", "updated_at"],
    "tech_experiment": ["id", "tech_id", "content", "experiment_date", "result",
                        "subject_keywords", "image", "created_at", "updated_at"],

    "project_profile": ["project_id", "name_cn", "name_en", "name_other", "tech_domain",
                        "sub_tech_domain", "start_date", "cancel_date", "finish_date",
                        "status", "budget_activities", "project_no", "main_orgs",
                        "undertaking_orgs", "undertaking_enterprises", "managers",
                        "researchers", "background", "research_goal", "research_content",
                        "keywords", "progress", "application_prospect", "key_dates",
                        "total_budget_million_usd", "invested_million_usd",
                        "parent_package_name", "previous_phase_name",
                        "confidence", "completeness", "created_at", "updated_at"],
    "project_history": ["id", "project_id", "change_date", "change_description",
                        "created_at", "updated_at"],
    "project_budget": ["id", "project_id", "budget_date", "amount", "created_at", "updated_at"],
    "project_output": ["id", "project_id", "name_history", "formed_at", "tech_domains",
                       "owner_orgs", "related_projects", "attachments", "created_at", "updated_at"],

    "org_profile": ["org_id", "name_cn", "name_en", "name_other", "country", "founded_date",
                    "dissolved_date", "operating_years", "website", "summary", "org_types",
                    "nature", "function", "scale", "tech_domains", "predecessor_names",
                    "departments", "strategic_plans", "evaluation_report", "new_key_projects",
                    "remark", "confidence", "completeness", "created_at", "updated_at"],
    "org_history": ["id", "org_id", "change_date", "change_description", "created_at", "updated_at"],
    "org_affiliation": ["id", "org_id", "change_date", "parent_name", "created_at", "updated_at"],
    "org_award": ["id", "org_id", "description", "name", "reason", "award_date", "level",
                  "award_type", "created_at", "updated_at"],
    "org_budget": ["id", "org_id", "funder_name", "budget_date", "amount_usd",
                   "created_at", "updated_at"],
    "org_funding": ["id", "org_id", "funder_name", "fund_date", "amount_or_equipment",
                    "created_at", "updated_at"],
    "org_output": ["id", "org_id", "name", "form", "author", "publish_date", "attachment",
                   "created_at", "updated_at"],
    "org_review": ["id", "org_id", "content", "review_org", "review_person", "review_type",
                   "review_date", "created_at", "updated_at"],
    "org_address": ["id", "org_id", "address", "longitude", "latitude", "created_at", "updated_at"],
    "org_activity": ["id", "org_id", "activity_type", "content", "activity_date", "locations",
                     "created_at", "updated_at"],
    "org_team": ["id", "org_id", "top_talents", "award_winners", "team_size", "talent_type",
                 "created_at", "updated_at"],
    "org_facility": ["id", "org_id", "name", "purpose", "experiment_status", "launch_date",
                     "construction_cost_wan_usd", "created_at", "updated_at"],

    "person_profile": ["person_id", "name_cn", "name_en", "gender", "avatar", "nationality",
                       "summary", "birth_date", "age", "birthplace", "ethnicity",
                       "current_residence", "current_org", "current_enterprise",
                       "current_military_unit", "current_position", "highest_degree",
                       "person_category", "professional_domains", "professional_skills",
                       "social_media", "personality_traits", "hobbies",
                       "management_philosophy", "remark", "confidence", "completeness",
                       "created_at", "updated_at"],
    "person_education": ["id", "person_id", "start_date", "degree_date", "degree", "school",
                         "major", "created_at", "updated_at"],
    "person_career": ["id", "person_id", "start_date", "end_date", "org", "enterprise",
                      "military_unit", "position", "created_at", "updated_at"],
    "person_award": ["id", "person_id", "description", "created_at", "updated_at"],
    "person_academic_output": ["id", "person_id", "name", "form", "publish_date", "rank",
                               "tech_domain", "collaborators", "citations", "is_representative",
                               "created_at", "updated_at"],
    "person_opinion": ["id", "person_id", "title", "publish_date", "raw_text", "occasion",
                       "main_points", "target_keywords", "created_at", "updated_at"],
    "person_review": ["id", "person_id", "content", "review_org", "review_enterprise",
                      "review_person", "review_type", "review_date", "created_at", "updated_at"],
    "person_focus": ["id", "person_id", "focus_type", "content", "consistency_with_policy",
                     "potential_impact", "created_at", "updated_at"],

    "entity_change_log": ["id", "entity_id", "entity_type", "field", "old_value", "new_value",
                          "method", "operator", "source_doc_id", "reason", "changed_at"],

    # ── 分析层 ──
    "frontier_tech": ["id", "scan_task_id", "tech_id", "tech_name", "tech_domain",
                      "period_from", "period_to", "burst_score", "patent_score",
                      "citation_score", "invest_score", "policy_score", "fusion_score",
                      "llm_validated", "llm_verdict", "llm_evidence", "trl_level", "status",
                      "created_at", "updated_at"],
    "scan_alert": ["id", "frontier_tech_id", "tech_name", "alert_type", "severity",
                   "message", "fired_at", "is_read", "created_at", "updated_at"],
    "weak_signal": ["id", "signal_id", "keywords", "related_tech_ids", "related_org_ids",
                    "related_person_ids", "evidence_doc_ids", "strength", "novelty",
                    "coherence", "diversity", "velocity", "period_from", "period_to",
                    "domain", "status", "created_at", "updated_at"],
    "topic_candidate": ["id", "topic_id", "title", "summary", "period", "related_tech_ids",
                        "related_org_ids", "related_project_ids", "related_policy_refs",
                        "score_hot", "score_policy", "score_impact", "score_dedup",
                        "score_llm_gen", "review_novelty", "review_importance",
                        "review_feasibility", "review_expression", "review_evidence",
                        "final_score", "status", "created_at", "updated_at"],
    "signal_network_edge": ["id", "signal_id", "source_id", "source_type", "target_id",
                            "target_type", "edge_type", "weight", "created_at", "updated_at"],
}

# 每张表的 JSON 列（值需 ::json 转换）。注意：同名列在不同表类型可能不同
# （如 content/remark），故按表精确指定。
JSON_TABLE_COLS: dict[str, set[str]] = {
    "tech_profile": {"tech_domain", "project_layout", "key_points"},
    "tech_dev_milestone": {"contributor_keywords"},
    "tech_review_impact": set(),
    "tech_funding": set(),
    "tech_academic_output": {"subject_keywords"},
    "tech_experiment": {"subject_keywords"},
    "project_profile": {"name_cn", "name_en", "name_other", "tech_domain", "sub_tech_domain",
                        "status", "budget_activities", "main_orgs", "undertaking_orgs",
                        "undertaking_enterprises", "managers", "researchers", "background",
                        "research_content", "keywords", "progress", "key_dates"},
    "project_history": set(),
    "project_budget": set(),
    "project_output": {"tech_domains", "owner_orgs", "related_projects", "attachments"},
    "org_profile": {"name_other", "org_types", "tech_domains", "predecessor_names",
                    "strategic_plans", "new_key_projects"},
    "org_history": set(),
    "org_affiliation": set(),
    "org_award": set(),
    "org_budget": set(),
    "org_funding": set(),
    "org_output": set(),
    "org_review": set(),
    "org_address": set(),
    "org_activity": {"locations"},
    "org_team": {"top_talents", "award_winners"},
    "org_facility": set(),
    "person_profile": {"avatar", "current_position", "professional_domains",
                       "professional_skills", "personality_traits", "hobbies",
                       "management_philosophy", "remark"},
    "person_education": set(),
    "person_career": set(),
    "person_award": set(),
    "person_academic_output": {"collaborators"},
    "person_opinion": {"target_keywords"},
    "person_review": set(),
    "person_focus": {"content", "potential_impact"},
    "entity_change_log": {"old_value", "new_value"},
    # 分析层
    "frontier_tech": {"tech_domain"},
    "scan_alert": set(),
    "weak_signal": {"keywords", "related_tech_ids", "related_org_ids",
                    "related_person_ids", "evidence_doc_ids"},
    "topic_candidate": {"related_tech_ids", "related_org_ids", "related_project_ids",
                        "related_policy_refs"},
}


def _json_default(o: Any) -> str:
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return str(o)


def sql_val(table: str, col: str, val: Any) -> str:
    if val is None:
        return "NULL"
    if col in JSON_TABLE_COLS.get(table, set()):
        return "'" + json.dumps(val, ensure_ascii=False, default=_json_default).replace("'", "''") + "'::json"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, date):
        return f"'{val.isoformat()}'"
    if isinstance(val, datetime):
        return f"'{val.isoformat()}'"
    # 字符串
    return "'" + str(val).replace("'", "''") + "'"


def sql_insert(table: str, rows: list[dict]) -> list[str]:
    cols = TABLES[table]
    out = []
    for row in rows:
        # 自增主键 id 为 None 时省略该列，让 PG 用 serial 默认值
        used = [(c, row.get(c)) for c in cols if not (c == "id" and row.get(c) is None)]
        used_cols = [c for c, _ in used]
        values = ", ".join(sql_val(table, c, v) for c, v in used)
        out.append(f"INSERT INTO {table} ({', '.join(used_cols)}) VALUES ({values});")
    return out


# 子表行构造（id 占位 None=自增，加时间戳）
def with_meta(rows: list[dict], fk_col: str, fk_val: str) -> list[dict]:
    out = []
    for r in rows:
        r = dict(r)
        r[fk_col] = fk_val
        r["id"] = None  # 自增主键
        r["created_at"] = NOW
        r["updated_at"] = NOW
        out.append(r)
    return out


def emit_sql(ds: Dataset, path: Path) -> None:
    lines: list[str] = []
    lines.append("-- MetaProfile 模拟数据（PG）—— 确定性、可重复导入。")
    lines.append(f"-- 生成时间标记: {NOW_STR}")
    lines.append("BEGIN;")
    lines.append("")
    # 清理（按 mock id 前缀，FK 级联清理子表；显式删子表更稳妥）
    for child in ["tech_dev_milestone", "tech_review_impact", "tech_funding",
                  "tech_academic_output", "tech_experiment"]:
        lines.append(f"DELETE FROM {child} WHERE tech_id LIKE 'TECH_S_%';")
    lines.append("DELETE FROM tech_profile WHERE tech_id LIKE 'TECH_S_%';")
    for child in ["project_history", "project_budget", "project_output"]:
        lines.append(f"DELETE FROM {child} WHERE project_id LIKE 'PROJECT_S_%';")
    lines.append("DELETE FROM project_profile WHERE project_id LIKE 'PROJECT_S_%';")
    for child in ["org_history", "org_affiliation", "org_award", "org_budget", "org_funding",
                  "org_output", "org_review", "org_address", "org_activity", "org_team",
                  "org_facility"]:
        lines.append(f"DELETE FROM {child} WHERE org_id LIKE 'ORG_S_%';")
    lines.append("DELETE FROM org_profile WHERE org_id LIKE 'ORG_S_%';")
    for child in ["person_education", "person_career", "person_award",
                  "person_academic_output", "person_opinion", "person_review", "person_focus"]:
        lines.append(f"DELETE FROM {child} WHERE person_id LIKE 'PERSON_S_%';")
    lines.append("DELETE FROM person_profile WHERE person_id LIKE 'PERSON_S_%';")
    lines.append("DELETE FROM entity_change_log WHERE entity_id LIKE 'TECH_S_%' "
                 "OR entity_id LIKE 'PROJECT_S_%' OR entity_id LIKE 'ORG_S_%' "
                 "OR entity_id LIKE 'PERSON_S_%';")
    lines.append("DELETE FROM scan_alert;")
    lines.append("DELETE FROM frontier_tech;")
    lines.append("DELETE FROM weak_signal;")
    lines.append("DELETE FROM signal_network_edge;")
    lines.append("DELETE FROM topic_candidate;")
    lines.append("")
    lines.append("-- ── 技术 ──")
    for t in ds.techs:
        main = {k: t.get(k) for k in TABLES["tech_profile"] if k in t}
        main["created_at"] = NOW
        main["updated_at"] = NOW
        lines += sql_insert("tech_profile", [main])
        lines += sql_insert("tech_dev_milestone",
                            with_meta(t["children"]["tech_dev_milestone"], "tech_id", t["tech_id"]))
        lines += sql_insert("tech_funding",
                            with_meta(t["children"]["tech_funding"], "tech_id", t["tech_id"]))
        lines += sql_insert("tech_academic_output",
                            with_meta(t["children"]["tech_academic_output"], "tech_id", t["tech_id"]))
        lines += sql_insert("tech_experiment",
                            with_meta(t["children"]["tech_experiment"], "tech_id", t["tech_id"]))
        lines.append(_changelog_sql(t["tech_id"], "tech"))
    lines.append("")
    lines.append("-- ── 项目 ──")
    for p in ds.projects:
        main = {k: p.get(k) for k in TABLES["project_profile"] if k in p}
        main["created_at"] = NOW
        main["updated_at"] = NOW
        lines += sql_insert("project_profile", [main])
        lines += sql_insert("project_history",
                            with_meta(p["children"]["project_history"], "project_id", p["project_id"]))
        lines += sql_insert("project_budget",
                            with_meta(p["children"]["project_budget"], "project_id", p["project_id"]))
        lines += sql_insert("project_output",
                            with_meta(p["children"]["project_output"], "project_id", p["project_id"]))
        lines.append(_changelog_sql(p["project_id"], "project"))
    lines.append("")
    lines.append("-- ── 机构 ──")
    for o in ds.orgs:
        main = {k: o.get(k) for k in TABLES["org_profile"] if k in o}
        main["created_at"] = NOW
        main["updated_at"] = NOW
        lines += sql_insert("org_profile", [main])
        lines += sql_insert("org_history",
                            with_meta(o["children"]["org_history"], "org_id", o["org_id"]))
        lines += sql_insert("org_award",
                            with_meta(o["children"]["org_award"], "org_id", o["org_id"]))
        lines += sql_insert("org_output",
                            with_meta(o["children"]["org_output"], "org_id", o["org_id"]))
        lines += sql_insert("org_team",
                            with_meta(o["children"]["org_team"], "org_id", o["org_id"]))
        lines += sql_insert("org_facility",
                            with_meta(o["children"]["org_facility"], "org_id", o["org_id"]))
        lines.append(_changelog_sql(o["org_id"], "org"))
    lines.append("")
    lines.append("-- ── 人员 ──")
    for p in ds.persons:
        main = {k: p.get(k) for k in TABLES["person_profile"] if k in p}
        main["created_at"] = NOW
        main["updated_at"] = NOW
        lines += sql_insert("person_profile", [main])
        lines += sql_insert("person_education",
                            with_meta(p["children"]["person_education"], "person_id", p["person_id"]))
        lines += sql_insert("person_career",
                            with_meta(p["children"]["person_career"], "person_id", p["person_id"]))
        lines += sql_insert("person_award",
                            with_meta(p["children"]["person_award"], "person_id", p["person_id"]))
        lines += sql_insert("person_academic_output",
                            with_meta(p["children"]["person_academic_output"], "person_id", p["person_id"]))
        lines += sql_insert("person_focus",
                            with_meta(p["children"]["person_focus"], "person_id", p["person_id"]))
        lines.append(_changelog_sql(p["person_id"], "person"))
    lines.append("")
    lines.append("-- ── 分析层 ──")
    lines += sql_insert("frontier_tech", ds.frontier_tech)
    lines += sql_insert("scan_alert", ds.alerts)
    lines += sql_insert("weak_signal", ds.signals)
    lines += sql_insert("signal_network_edge", ds.signal_edges)
    lines += sql_insert("topic_candidate", ds.topics)
    lines.append("")
    lines.append("COMMIT;")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[SQL] 写入 {path}  ({len(lines)} 行)")


def _changelog_sql(entity_id: str, entity_type: str) -> str:
    row = {
        "id": None, "entity_id": entity_id, "entity_type": entity_type, "field": "*",
        "old_value": None, "new_value": {"action": "create"}, "method": "rule",
        "operator": None, "source_doc_id": "mock_seed", "reason": None, "changed_at": NOW,
    }
    return sql_insert("entity_change_log", [row])[0]


def emit_cypher(ds: Dataset, path: Path) -> None:
    label = {"TECH": "Tech", "ORG": "Org", "PERSON": "Person", "PROJECT": "Project"}
    name_key = {"TECH": "tech_name_cn", "ORG": "name_cn", "PERSON": "name_cn", "PROJECT": None}

    def node_line(etype: str, eid: str, name: str, conf: float) -> str:
        L = label[etype]
        nm = name.replace("'", "\\'")
        return (f"MERGE (n:{L} {{entity_id: '{eid}'}}) "
                f"SET n.name='{nm}', n.entity_type='{etype}', n.confidence={conf};")

    lines = ["// MetaProfile 模拟数据（Neo4j）—— 确定性、可重复导入。", f"// {NOW_STR}", ""]
    # 清理 mock 节点
    lines.append("MATCH (n) WHERE n.entity_id STARTS WITH 'TECH_S_' "
                 "OR n.entity_id STARTS WITH 'ORG_S_' "
                 "OR n.entity_id STARTS WITH 'PERSON_S_' "
                 "OR n.entity_id STARTS WITH 'PROJECT_S_' "
                 "DETACH DELETE n;")
    lines.append("")
    for t in ds.techs:
        lines.append(node_line("TECH", t["tech_id"], t["tech_name_cn"], t["confidence"]))
    for o in ds.orgs:
        lines.append(node_line("ORG", o["org_id"], o["name_cn"], o["confidence"]))
    for p in ds.persons:
        lines.append(node_line("PERSON", p["person_id"], p["name_cn"], p["confidence"]))
    for p in ds.projects:
        lines.append(node_line("PROJECT", p["project_id"], p["name_cn"][0], p["confidence"]))
    lines.append("")
    lines.append("// ── 关系 ──")
    for r in ds.relations:
        sl = label[r["subject_type"]]
        ol = label[r["object_type"]]
        rt = "`" + r["relation"] + "`"  # 反引号包裹中文关系类型
        lines.append(
            f"MATCH (a:{sl} {{entity_id: '{r['subject_id']}'}}), "
            f"(b:{ol} {{entity_id: '{r['object_id']}'}}) "
            f"MERGE (a)-[:{rt} {{confidence: {r['confidence']}, "
            f"method: '{r['method']}', source_doc_id: '{r['source_doc_id']}'}}]->(b);"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Cypher] 写入 {path}  ({len(lines)} 行)")


# ───────────────────────── 实时写入三库 ───────────────────────────────────

async def write_pg(ds: Dataset) -> None:
    from sqlalchemy import text
    from metaprofile.shared.db.postgres import get_sessionmaker, init_db

    await init_db()
    smk = get_sessionmaker()
    async with smk() as session:
        # 清理 mock 数据
        for stmt in [
            "DELETE FROM tech_dev_milestone WHERE tech_id LIKE 'TECH_S_%'",
            "DELETE FROM tech_review_impact WHERE tech_id LIKE 'TECH_S_%'",
            "DELETE FROM tech_funding WHERE tech_id LIKE 'TECH_S_%'",
            "DELETE FROM tech_academic_output WHERE tech_id LIKE 'TECH_S_%'",
            "DELETE FROM tech_experiment WHERE tech_id LIKE 'TECH_S_%'",
            "DELETE FROM tech_profile WHERE tech_id LIKE 'TECH_S_%'",
            "DELETE FROM project_history WHERE project_id LIKE 'PROJECT_S_%'",
            "DELETE FROM project_budget WHERE project_id LIKE 'PROJECT_S_%'",
            "DELETE FROM project_output WHERE project_id LIKE 'PROJECT_S_%'",
            "DELETE FROM project_profile WHERE project_id LIKE 'PROJECT_S_%'",
            "DELETE FROM org_history WHERE org_id LIKE 'ORG_S_%'",
            "DELETE FROM org_award WHERE org_id LIKE 'ORG_S_%'",
            "DELETE FROM org_output WHERE org_id LIKE 'ORG_S_%'",
            "DELETE FROM org_team WHERE org_id LIKE 'ORG_S_%'",
            "DELETE FROM org_facility WHERE org_id LIKE 'ORG_S_%'",
            "DELETE FROM org_profile WHERE org_id LIKE 'ORG_S_%'",
            "DELETE FROM person_education WHERE person_id LIKE 'PERSON_S_%'",
            "DELETE FROM person_career WHERE person_id LIKE 'PERSON_S_%'",
            "DELETE FROM person_award WHERE person_id LIKE 'PERSON_S_%'",
            "DELETE FROM person_academic_output WHERE person_id LIKE 'PERSON_S_%'",
            "DELETE FROM person_focus WHERE person_id LIKE 'PERSON_S_%'",
            "DELETE FROM person_profile WHERE person_id LIKE 'PERSON_S_%'",
            ("DELETE FROM entity_change_log WHERE entity_id LIKE 'TECH_S_%' "
             "OR entity_id LIKE 'PROJECT_S_%' OR entity_id LIKE 'ORG_S_%' "
             "OR entity_id LIKE 'PERSON_S_%'"),
            "DELETE FROM scan_alert",
            "DELETE FROM frontier_tech",
            "DELETE FROM weak_signal",
            "DELETE FROM signal_network_edge",
            "DELETE FROM topic_candidate",
        ]:
            await session.execute(text(stmt))
        await session.commit()

        # 直接执行生成的 SQL（单连接，快）
        sql_path = ROOT / "deploy" / "mock_data.sql"
        raw = sql_path.read_text(encoding="utf-8")
        # 先剥离整行注释（防止节注释 "-- ── 技术 ──" 与下一条 INSERT 拼接后被
        # 当作注释整体跳过，导致父表缺失、子表外键违反）
        body = "\n".join(ln for ln in raw.splitlines() if not ln.strip().startswith("--"))
        # 去掉 BEGIN/COMMIT（已在事务中），逐句执行
        stmts = [s.strip() for s in body.split(";") if s.strip()
                 and s.strip() not in ("BEGIN", "COMMIT")]
        ok = 0
        for s in stmts:
            try:
                await session.execute(text(s))
                ok += 1
            except Exception as exc:
                print(f"[PG] 语句失败: {exc}  | {s[:120]}")
        await session.commit()
    print(f"[PG] 写入完成，执行 {ok} 条 INSERT")


async def write_neo4j(ds: Dataset) -> None:
    from metaprofile.shared.db.neo4j import get_neo4j_session

    label = {"TECH": "Tech", "ORG": "Org", "PERSON": "Person", "PROJECT": "Project"}

    async def run(cypher, **params):
        async with get_neo4j_session() as s:
            await s.run(cypher, **params)

    # 清理
    await run(
        "MATCH (n) WHERE n.entity_id STARTS WITH 'TECH_S_' "
        "OR n.entity_id STARTS WITH 'ORG_S_' "
        "OR n.entity_id STARTS WITH 'PERSON_S_' "
        "OR n.entity_id STARTS WITH 'PROJECT_S_' DETACH DELETE n"
    )
    # 节点
    nodes = []
    for t in ds.techs:
        nodes.append(("TECH", t["tech_id"], t["tech_name_cn"], t["confidence"]))
    for o in ds.orgs:
        nodes.append(("ORG", o["org_id"], o["name_cn"], o["confidence"]))
    for p in ds.persons:
        nodes.append(("PERSON", p["person_id"], p["name_cn"], p["confidence"]))
    for p in ds.projects:
        nodes.append(("PROJECT", p["project_id"], p["name_cn"][0], p["confidence"]))
    for etype, eid, name, conf in nodes:
        L = label[etype]
        await run(
            f"MERGE (n:{L} {{entity_id: $eid}}) "
            "SET n += {name: $name, entity_type: $etype, confidence: $conf}",
            eid=eid, name=name, etype=etype, conf=conf,
        )
    # 关系（反引号包裹中文类型）
    cnt = 0
    for r in ds.relations:
        sl, ol = label[r["subject_type"]], label[r["object_type"]]
        rt = "`" + r["relation"] + "`"
        await run(
            f"MATCH (a:{sl} {{entity_id: $f}}), (b:{ol} {{entity_id: $t}}) "
            f"MERGE (a)-[rel:{rt}]->(b) "
            "SET rel += {confidence: $c, method: $m, source_doc_id: $s}",
            f=r["subject_id"], t=r["object_id"], c=r["confidence"],
            m=r["method"], s=r["source_doc_id"],
        )
        cnt += 1
    print(f"[Neo4j] 节点 {len(nodes)}，关系 {cnt}")


async def write_es(ds: Dataset) -> None:
    from metaprofile.foundation.storage.es_repo import FoundationESRepo
    from metaprofile.shared.schemas.base import EntityType

    repo = FoundationESRepo()
    # EntityType -> (items, id_key, name_key)
    mapping = {
        EntityType.TECH: (ds.techs, "tech_id", "tech_name_cn"),
        EntityType.ORG: (ds.orgs, "org_id", "name_cn"),
        EntityType.PERSON: (ds.persons, "person_id", "name_cn"),
        EntityType.PROJECT: (ds.projects, "project_id", "name_cn"),
    }
    total = 0
    for et, (items, id_key, name_key) in mapping.items():
        try:
            await repo.ensure_entity_index(et)
        except Exception as exc:
            print(f"[ES] 索引创建失败 {et}: {exc}")
            continue
        for it in items:
            attrs = {k: v for k, v in it.items()
                     if k != "children" and not k.startswith("_")}
            try:
                await repo.upsert_entity(
                    entity_type=et, entity_id=it[id_key], attributes=attrs)
                total += 1
            except Exception as exc:
                print(f"[ES] 文档写入失败 {it.get(id_key)}: {exc}")
    print(f"[ES] 文档 {total}")


# ───────────────────────── 入口 ───────────────────────────────────────────

async def main() -> None:
    print(f"== 生成 {ARGS.count}×4 实体，seed={ARGS.seed} ==")
    ds = build_dataset(ARGS.count, ARGS.seed)
    print(f"实体: 技术 {len(ds.techs)} / 组织 {len(ds.orgs)} / 人员 {len(ds.persons)} / "
          f"项目 {len(ds.projects)} | 关系 {len(ds.relations)}")

    deploy = ROOT / "deploy"
    deploy.mkdir(exist_ok=True)
    emit_sql(ds, deploy / "mock_data.sql")
    emit_cypher(ds, deploy / "mock_data.cypher")

    if ARGS.sql_only:
        print("== --sql-only：跳过实时写入 ==")
        return

    if not ARGS.no_pg:
        try:
            await write_pg(ds)
        except Exception as exc:
            print(f"[PG] 写入异常: {exc}")
    if not ARGS.no_neo4j:
        try:
            await write_neo4j(ds)
        except Exception as exc:
            print(f"[Neo4j] 写入异常: {exc}")
    if not ARGS.no_es:
        try:
            await write_es(ds)
        except Exception as exc:
            print(f"[ES] 写入异常: {exc}")
    print("== 完成 ==")


if __name__ == "__main__":
    asyncio.run(main())
