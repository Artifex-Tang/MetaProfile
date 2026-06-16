"""
演示/评审模式：分析层触发任务的同步确定性生成。

真实链路（信号计算 + LLM Agent 验证）依赖采集源数据与 LLM 配置；在评审/演示场景下，
触发"扫描 / 发现 / 选题"时，本模块基于已有画像数据同步生成一批分析结果并落库，
保证"点击触发 → 列表立即出现新结果"的可见反馈。
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import SignalNetworkEdgeORM, WeakSignalORM
from metaprofile.scan_monitor.domain.orm_models import FrontierTechORM, ScanAlertORM
from metaprofile.topic_selection.domain.orm_models import TopicCandidateORM

_ALERT_TYPES = ["burst", "trl_upgrade", "org_layout"]
_ALERT_MSG = ["关键词突现，关注度显著上升", "TRL 等级提升", "关键机构布局变化"]
_DOMAINS = ["人工智能", "量子计算", "半导体", "生物医药", "新能源", "航空航天",
            "新材料", "集成电路", "大模型", "机器人", "5G通信", "卫星互联网",
            "基因编辑", "脑机接口", "增材制造", "氢能", "储能", "光电", "网络安全"]
_TOPIC_SUFFIX = ["前沿进展", "技术突破", "产业动态", "发展趋势", "战略机遇"]


async def _tech_rows(session: AsyncSession, limit: int = 30):
    from metaprofile.profile_tech.domain.orm_models import TechProfileORM
    rows = (await session.execute(
        select(TechProfileORM).limit(limit)
    )).scalars().all()
    return [{"tech_id": r.tech_id, "tech_name": r.tech_name_cn,
             "domain": (r.tech_domain or [None])[0]} for r in rows]


async def _org_rows(session: AsyncSession, limit: int = 10):
    from metaprofile.profile_org.domain.orm_models import OrgProfileORM
    rows = (await session.execute(select(OrgProfileORM).limit(limit))).scalars().all()
    return [r.org_id for r in rows]


async def _person_rows(session: AsyncSession, limit: int = 10):
    from metaprofile.profile_person.domain.orm_models import PersonProfileORM
    rows = (await session.execute(select(PersonProfileORM).limit(limit))).scalars().all()
    return [r.person_id for r in rows]


async def _project_rows(session: AsyncSession, limit: int = 10):
    from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
    rows = (await session.execute(select(ProjectProfileORM).limit(limit))).scalars().all()
    return [r.project_id for r in rows]


async def generate_frontier(session: AsyncSession, *, period_from: date,
                            period_to: date, count: int = 8, seed: int = 0) -> int:
    """同步生成一批前沿技术记录（+ 告警），返回新增数。"""
    rng = random.Random(seed)
    techs = await _tech_rows(session, 30)
    if not techs:
        return 0
    orgs = await _org_rows(session, 8)
    n = 0
    for i in range(count):
        t = techs[(seed + i) % len(techs)]
        burst = round(rng.uniform(0.4, 0.98), 3)
        patent = round(rng.uniform(0.3, 0.95), 3)
        citation = round(rng.uniform(0.3, 0.9), 3)
        invest = round(rng.uniform(0.2, 0.85), 3)
        policy = round(rng.uniform(0.2, 0.8), 3)
        fusion = round((burst + patent + citation + invest + policy) / 5, 3)
        orm = FrontierTechORM(
            scan_task_id=f"scan-demo-{seed}-{i}",
            tech_id=t["tech_id"], tech_name=t["tech_name"],
            tech_domain=[t["domain"]] if t["domain"] else [],
            period_from=period_from, period_to=period_to,
            burst_score=burst, patent_score=patent, citation_score=citation,
            invest_score=invest, policy_score=policy, fusion_score=fusion,
            llm_validated=False, llm_verdict="待定",
            trl_level=rng.randint(2, 8), status="pending",
        )
        session.add(orm)
        n += 1
        if fusion >= 0.7:
            session.add(ScanAlertORM(
                tech_name=t["tech_name"],
                alert_type=rng.choice(_ALERT_TYPES),
                severity=rng.choice(["info", "warn", "critical"]),
                message=f"{t['tech_name']}{rng.choice(_ALERT_MSG)}",
                fired_at=datetime.now(timezone.utc), is_read=False,
            ))
    await session.commit()
    return n


async def generate_signals(session: AsyncSession, *, period_from: date,
                            period_to: date, count: int = 8, seed: int = 0) -> int:
    """同步生成一批弱信号记录，返回新增数。"""
    rng = random.Random(seed)
    techs = await _tech_rows(session, 20)
    orgs = await _org_rows(session, 8)
    persons = await _person_rows(session, 8)
    n = 0
    for i in range(count):
        kws = rng.sample(_DOMAINS, rng.randint(1, 3))
        tid = rng.choice(techs)["tech_id"] if techs else None
        oid = rng.sample(orgs, 1)[0] if orgs else None      # orgs 已是 org_id 字符串列表
        pid = rng.sample(persons, 1)[0] if persons else None  # persons 已是 person_id 字符串列表
        sig_id = f"SIG-DEMO-{seed}-{i}-{rng.randint(1000, 9999)}"
        orm = WeakSignalORM(
            signal_id=sig_id,
            keywords=kws,
            related_tech_ids=[tid] if tid else [],
            related_org_ids=[oid] if oid else [],
            related_person_ids=[pid] if pid else [],
            evidence_doc_ids=[],
            strength=round(rng.uniform(0.3, 0.95), 3),
            novelty=round(rng.uniform(0.3, 0.95), 3),
            coherence=round(rng.uniform(0.3, 0.9), 3),
            diversity=round(rng.uniform(0.2, 0.85), 3),
            velocity=round(rng.uniform(0.2, 0.9), 3),
            period_from=period_from, period_to=period_to,
            domain=rng.choice(_DOMAINS), status="active",
        )
        session.add(orm)
        # 关联网络边（与 gen_mock 一致：共现/资助/引用），保证触发后的信号也有图可看
        for src, st, tgt, tt, et in [
            (tid, "tech", oid, "org", "co_occurrence"),
            (oid, "org", pid, "person", "funding"),
            (tid, "tech", pid, "person", "citation"),
        ]:
            if src and tgt:
                session.add(SignalNetworkEdgeORM(
                    signal_id=sig_id, source_id=src, source_type=st,
                    target_id=tgt, target_type=tt, edge_type=et,
                    weight=round(rng.uniform(0.3, 0.95), 3),
                ))
        n += 1
    await session.commit()
    return n


async def generate_topics(session: AsyncSession, *, count: int = 6, seed: int = 0,
                          period_from: date | None = None,
                          period_to: date | None = None) -> int:
    """同步生成一批选题候选，返回新增数。"""
    rng = random.Random(seed)
    techs = await _tech_rows(session, 20)
    orgs = await _org_rows(session, 8)
    projects = await _project_rows(session, 8)
    n = 0
    today = date.today()
    q = f"{today.year}Q{(today.month - 1) // 3 + 1}"
    for i in range(count):
        domain = rng.choice(_DOMAINS)
        orm = TopicCandidateORM(
            topic_id=f"TOPIC-DEMO-{seed}-{i}-{rng.randint(1000, 9999)}",
            title=f"{domain}{rng.choice(_TOPIC_SUFFIX)}选题",
            summary=f"围绕{domain}领域近期突现信号与机构布局变化，建议开展情报选题研究。",
            period=q,
            related_tech_ids=[rng.choice(techs)["tech_id"]] if techs else [],
            related_org_ids=rng.sample(orgs, 1) if orgs else [],
            related_project_ids=rng.sample(projects, 1) if projects else [],
            related_policy_refs=[],
            score_hot=round(rng.uniform(0.4, 0.95), 3),
            score_policy=round(rng.uniform(0.3, 0.9), 3),
            score_impact=round(rng.uniform(0.3, 0.9), 3),
            score_dedup=round(rng.uniform(0.5, 0.95), 3),
            score_llm_gen=round(rng.uniform(0.3, 0.9), 3),
            review_novelty=round(rng.uniform(0.4, 0.95), 3),
            review_importance=round(rng.uniform(0.4, 0.9), 3),
            review_feasibility=round(rng.uniform(0.4, 0.9), 3),
            review_expression=round(rng.uniform(0.4, 0.9), 3),
            final_score=round(rng.uniform(0.5, 0.95), 3),
            status="pending",
        )
        session.add(orm)
        n += 1
    await session.commit()
    return n
