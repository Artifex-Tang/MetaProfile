"""前沿候选真数据构建(Phase E1,子项目2:修 G4 demo 断链)。

候选来源(去重):
- weak_signal 按 strength top-N(名称=关键词)
- tech_emergence_indicator ipc_domain 象限 ∈ {weak,strong}(fusion=归一混合分)
- disruption_assessment 按 disrupt_score top-N

fusion v1 = 0.5·burst + 0.3·patent_growth + 0.2·disrupt(各维归一 [0,1];
citation/invest/policy 三维 5-scorer 接口留位,真数据源接入后补)。
≥0.55 → info alert;≥0.80 → critical alert(复用 scan_alert)。
落库后由既有 LLM 验证按钮(FrontierAgentValidator)复核 → validated → 选题联动(E2)。
"""
from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import (
    DisruptionAssessmentORM,
    TechEmergenceIndicatorORM,
    WeakSignalORM,
)
from metaprofile.scan_monitor.domain.orm_models import FrontierTechORM, ScanAlertORM

logger = structlog.get_logger(__name__)

_FUSION_W = {"burst": 0.5, "patent": 0.3, "disrupt": 0.2}



def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def blend_fusion(burst: float, patent_growth: float, disrupt: float) -> float:
    """v1 融合分:三维归一混合(5-scorer 其余维度接入后扩展)。"""
    return round(
        _FUSION_W["burst"] * _clamp01(burst)
        + _FUSION_W["patent"] * _clamp01(patent_growth)
        + _FUSION_W["disrupt"] * _clamp01(disrupt),
        4,
    )


async def build_frontier_candidates(
    db: AsyncSession, *, period_from: date, period_to: date,
    per_source: int = 15,
) -> dict:
    """三源 → frontier_tech 候选行 + 告警。返回统计。"""
    task_id = f"scan-{uuid.uuid4().hex[:12]}"
    # 替换式扫描:清旧 pending 候选(保留 validated/rejected 审计历史),
    # 防多次扫描同名堆积(实测同域双行)
    from sqlalchemy import delete
    await db.execute(delete(FrontierTechORM).where(FrontierTechORM.status == "pending"))
    # 归一基准
    max_strength = (await db.execute(
        select(func.max(WeakSignalORM.strength))
    )).scalar() or 1.0
    max_disrupt = (await db.execute(
        select(func.max(DisruptionAssessmentORM.disrupt_score))
    )).scalar() or 1.0
    # ipc:X → 中文名(缺名回落码,用户反馈"技术名称是编码"修复)
    from metaprofile.profile_tech.domain.orm_models import TechProfileORM
    ipc_names = {t.tech_id: (t.tech_name_cn or t.tech_id)
                 for t in (await db.execute(
                     select(TechProfileORM.tech_id, TechProfileORM.tech_name_cn)
                     .where(TechProfileORM.tech_layer == "DOMAIN")
                 )).all()}

    candidates: dict[str, dict] = {}

    for sig in (await db.execute(
        select(WeakSignalORM)
        .where(WeakSignalORM.period_from == period_from)
        .order_by(WeakSignalORM.strength.desc()).limit(per_source)
    )).scalars().all():
        name = (sig.keywords or [""])[0]
        if len(name) < 2 or name in candidates:
            continue
        burst = (sig.strength or 0.0) / max_strength if max_strength else 0.0
        candidates[name] = {
            "tech_id": sig.signal_id, "name": name,
            "burst": burst, "patent": 0.0, "disrupt": 0.0,
            "domains": [sig.domain] if sig.domain else [],
        }

    for ind in (await db.execute(
        select(TechEmergenceIndicatorORM)
        .where(TechEmergenceIndicatorORM.object_type == "ipc_domain")
        .order_by(TechEmergenceIndicatorORM.window_month.desc()).limit(800)
    )).scalars().all():
        m = ind.metrics or {}
        if m.get("tem_quadrant") not in ("weak", "strong"):
            continue
        # 小样本域护栏(2026-10-15:冲水马桶/烟嘴烟盒类小域 growth clamp 顶格
        # 假高):专利量不足 min_domain_patents 的域不进候选
        if int(m.get("patents") or 0) < 50:
            continue
        name = ipc_names.get(ind.object_id) or ind.object_id.split(":", 1)[-1]
        code = ind.object_id.split(":", 1)[-1]
        if name in candidates or code in candidates:
            hit = candidates.get(name) or candidates.get(code)
            hit["patent"] = _clamp01(float(m.get("tem_growth", 0)))
            continue
        if len([c for c in candidates.values() if c["tech_id"].startswith("ipc:")]) >= per_source:
            continue
        candidates[name] = {
            "tech_id": ind.object_id, "name": name,
            "burst": 0.0,
            "patent": _clamp01(float(m.get("tem_growth", 0))),
            "disrupt": 0.0,
            # tech_domain 存领域名(用户反馈:象限标签与"领域"语义不搭;
            # 象限状态留在新兴指标页)
            "domains": [name],
        }

    for dis in (await db.execute(
        select(DisruptionAssessmentORM)
        .order_by(DisruptionAssessmentORM.disrupt_score.desc()).limit(per_source)
    )).scalars().all():
        name = ipc_names.get(dis.object_id) or dis.object_id.split(":", 1)[-1]
        if name in candidates:
            candidates[name]["disrupt"] = (dis.disrupt_score or 0.0) / max_disrupt
        else:
            candidates[name] = {
                "tech_id": dis.object_id, "name": name,
                "burst": 0.0, "patent": 0.0,
                "disrupt": (dis.disrupt_score or 0.0) / max_disrupt,
                "domains": [],
            }

    rows, alerts = [], []
    for c in candidates.values():
        fusion = blend_fusion(c["burst"], c["patent"], c["disrupt"])
        rows.append(FrontierTechORM(
            scan_task_id=task_id, tech_id=c["tech_id"], tech_name=c["name"],
            tech_domain=[d for d in c["domains"] if d],
            period_from=period_from, period_to=period_to,
            burst_score=round(c["burst"], 4),
            patent_score=round(c["patent"], 4),
            fusion_score=fusion, status="pending",
        ))
        if fusion >= 0.80:
            alerts.append(ScanAlertORM(
                alert_type="burst", severity="critical",
                message=f"前沿候选 {c['name']} fusion={fusion:.3f}(≥0.80)",
            ))
        elif fusion >= 0.55:
            alerts.append(ScanAlertORM(
                alert_type="burst", severity="warn",
                message=f"前沿候选 {c['name']} fusion={fusion:.3f}",
            ))
    if rows:
        db.add_all(rows)
    if alerts:
        db.add_all(alerts)
    await db.flush()
    logger.info("frontier_candidates_built", task_id=task_id,
                candidates=len(rows), alerts=len(alerts))
    return {"task_id": task_id, "candidates": len(rows), "alerts": len(alerts)}


async def sync_validated_to_topics(db: AsyncSession) -> int:
    """E2(子项目3 v1):validated frontier → topic_candidate 联动。"""
    from metaprofile.topic_selection.domain.orm_models import TopicCandidateORM

    validated = (await db.execute(
        select(FrontierTechORM).where(FrontierTechORM.status == "validated")
    )).scalars().all()
    existing = {t.title for t in (await db.execute(
        select(TopicCandidateORM)
    )).scalars().all()}
    created = 0
    for f in validated:
        title = f"前沿方向:{f.tech_name}"
        if title in existing:
            continue
        final = round(0.6 * (f.fusion_score or 0.0) + 0.4 * (f.patent_score or 0.0), 4)
        db.add(TopicCandidateORM(
            topic_id="TOPIC-" + uuid.uuid4().hex[:12],
            title=title,
            summary=f.llm_evidence or f"前沿候选(fusion={f.fusion_score})",
            period=f"{f.period_from.year}Q{(f.period_from.month - 1) // 3 + 1}",
            related_tech_ids=[f.tech_id] if f.tech_id else [],
            score_hot=f.fusion_score or 0.0,
            score_impact=f.patent_score or 0.0,
            final_score=final, status="pending",
        ))
        created += 1
    if created:
        await db.flush()
        logger.info("frontier_synced_to_topics", created=created)
    return created
