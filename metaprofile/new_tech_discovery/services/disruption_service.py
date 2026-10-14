"""颠覆性评估服务(Phase C):专利 → 组件分 z 合成 → DisruptScore → 漏斗 LLM rubric。

流程:
1. 拉 ODS 专利(年/申请人/ipc_type/标题,id DESC cap 保最新)
2. 每 IPC 域(最新窗):
   - novelty_comb: 含"历史从未见过 IPC 对"的专利占比(Wang 无引文版)
   - growth: 专利数环比增速
   - new_entrant: 新进入申请人占比(Porter)
   - small_team: 申请人 ≤1 的专利占比(Wu/Wang/Evans 近似)
   - term_novelty: 标题 token 首现占比
3. 跨域 z 归一 → 加权合 DisruptScore(权重可配)
4. upsert disruption_assessment;Top-N 由 LLM Rotolo rubric(×N 中位)复核
统计层零 LLM;LLM 只碰漏斗末端(配额纪律)。
"""
from __future__ import annotations

import asyncio
import re
from datetime import date

import pymysql
import sqlalchemy as sa
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn
from metaprofile.new_tech_discovery.domain.orm_models import DisruptionAssessmentORM
from metaprofile.new_tech_discovery.services.disruption_metrics import (
    disrupt_score,
    new_term_ratio,
    novelty_ratio,
    small_team_ratio,
    z_scores,
)
from metaprofile.new_tech_discovery.services.emergence_metrics import (
    pair_combinations,
    porter_indicators,
)
from metaprofile.new_tech_discovery.services.emergence_service import subclasses_of
from metaprofile.new_tech_discovery.services.signal_metrics import tokenize
from metaprofile.shared.config.settings import settings
from metaprofile.shared.db.postgres import get_session

logger = structlog.get_logger(__name__)

_APP_SEP = re.compile(r"[;；,，|]")


def _load_patent_rows(dsn: dict, year_from: int, year_to: int,
                      limit: int) -> list[tuple[int, str, str, str]]:
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        cur.execute(
            "SELECT YEAR(filing_date), applicant, ipc_type, title "
            "FROM ods_invention_patent_cn "
            "WHERE filing_date IS NOT NULL AND filing_date >= %s AND filing_date < %s "
            "AND ipc_type IS NOT NULL AND ipc_type != '' "
            "ORDER BY id DESC LIMIT %s",
            (f"{year_from}-01-01", f"{year_to + 1}-01-01", limit),
        )
        rows = [
            (int(y), str(a or ""), str(i or ""), str(t or ""))
            for y, a, i, t in cur.fetchall()
            if y is not None
        ]
        cur.close()
        return rows
    finally:
        conn.close()


def build_components(rows: list[tuple[int, str, str, str]],
                     weights: dict[str, float] | None = None) -> list[dict]:
    """专利行 → 每域组件原始值(最新窗)+ z 合分行(不带 LLM 字段)。"""
    years = sorted({y for y, _, _, _ in rows})
    if not years:
        return []
    last = years[-1]

    dom_pat: dict[str, dict[int, int]] = {}
    dom_apps: dict[str, dict[int, set[str]]] = {}
    dom_counts: dict[str, list[int]] = {}           # 最新窗每专利申请人计数
    dom_pairs: dict[str, list[set[tuple[str, str]]]] = {}
    hist_pairs: dict[str, set[tuple[str, str]]] = {}
    dom_terms: dict[str, dict[int, set[str]]] = {}

    for y, applicant, ipc_type, title in rows:
        subs = subclasses_of(ipc_type)
        if not subs:
            continue
        apps = {a.strip() for a in _APP_SEP.split(applicant) if a.strip()}
        sub = subs[0]
        dom_pat.setdefault(sub, {}).setdefault(y, 0)
        dom_pat[sub][y] += 1
        dom_apps.setdefault(sub, {}).setdefault(y, set())
        dom_apps[sub][y] |= apps
        pairs = set(pair_combinations(set(subs)))
        if y == last:
            dom_counts.setdefault(sub, []).append(len(apps))
            if pairs:
                dom_pairs.setdefault(sub, []).append(pairs)
            toks = set(tokenize(title))
            if toks:
                dom_terms.setdefault(sub, {}).setdefault(last, set())
                dom_terms[sub][last] |= toks
        else:
            hist_pairs.setdefault(sub, set()).update(pairs)
            toks = set(tokenize(title))
            if toks:
                dom_terms.setdefault(sub, {}).setdefault(y, set())
                dom_terms[sub][y] |= toks

    raw: dict[str, dict[str, float]] = {}
    for sub in dom_pat:
        series = [dom_pat[sub].get(y, 0) for y in years]
        ents = [dom_apps.get(sub, {}).get(y, set()) for y in years]
        porter = porter_indicators(ents)
        growth = (series[-1] / series[-2] - 1) if len(series) >= 2 and series[-2] > 0 else 0.0
        hist_terms: set[str] = set()
        for y in years[:-1]:
            hist_terms |= dom_terms.get(sub, {}).get(y, set())
        cur_terms = dom_terms.get(sub, {}).get(last, set())
        raw[sub] = {
            "novelty_comb": novelty_ratio(dom_pairs.get(sub, []), hist_pairs.get(sub, set())),
            "growth": growth,
            "new_entrant": porter[-1]["new_entrant_ratio"],
            "small_team": small_team_ratio(dom_counts.get(sub, []),
                                           max_applicants=1),
            "term_novelty": new_term_ratio(cur_terms, hist_terms),
        }

    z = {dim: z_scores({s: v[dim] for s, v in raw.items()}) for dim in
         ("novelty_comb", "growth", "new_entrant", "small_team", "term_novelty")}
    out: list[dict] = []
    for sub, v in raw.items():
        comps = {dim: round(z[dim].get(sub, 0.0), 4) for dim in v}
        out.append({
            "object_type": "ipc_domain",
            "object_id": f"ipc:{sub}",
            "window_month": date(last, 1, 1),
            "novelty_comb": comps["novelty_comb"],
            "growth": comps["growth"],
            "new_entrant": comps["new_entrant"],
            "small_team": comps["small_team"],
            "term_novelty": comps["term_novelty"],
            "disrupt_score": round(disrupt_score(comps, weights), 4),
            "raw": v,
        })
    return out


async def persist_assessments(session: AsyncSession, rows: list[dict]) -> int:
    written = 0
    for start in range(0, len(rows), 500):
        chunk = [
            {k: v for k, v in r.items() if k != "raw"} for r in rows[start:start + 500]
        ]
        stmt = pg_insert(DisruptionAssessmentORM).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_disruption_object_window",
            set_={
                c: getattr(stmt.excluded, c) for c in
                ("novelty_comb", "growth", "new_entrant", "small_team",
                 "term_novelty", "disrupt_score")
            } | {"updated_at": sa.func.now()},
        )
        await session.execute(stmt)
        written += len(chunk)
    if written:
        logger.info("disruption_assessments_persisted", rows=written)
    return written


async def run_llm_funnel(session: AsyncSession, rows: list[dict], *, top_n: int,
                         runs: int) -> int:
    """Top-N → LLM Rotolo rubric ×runs 中位 → 回写 verdict。失败留 pending。"""
    from metaprofile.new_tech_discovery.services.rotolo_validator import (
        RotoloRubricValidator,
        median_verdict,
    )
    from metaprofile.shared.llm.gateway import LLMGateway

    top = sorted(rows, key=lambda r: r["disrupt_score"], reverse=True)[:top_n]
    if not top:
        return 0
    validator = RotoloRubricValidator(LLMGateway())
    judged = 0
    for r in top:
        evidence = (
            f"统计窗口:{r['window_month'].year} 年\n"
            f"组件原始值:{ {k: round(v, 4) for k, v in r['raw'].items()} }\n"
            f"DisruptScore(z 加权):{r['disrupt_score']}"
        )
        try:
            scored = [
                await validator.validate(name=r["object_id"], evidence_pack=evidence)
                for _ in range(runs)
            ]
        except Exception as exc:  # noqa: BLE001  LLM 失败留 pending 不阻塞
            logger.warning("rotolo_failed", obj=r["object_id"], error=str(exc))
            continue
        scores, composite, verdict, rationale = median_verdict(scored)
        await session.execute(
            pg_insert(DisruptionAssessmentORM)
            .values(**{k: v for k, v in r.items() if k != "raw"},
                    llm_verdict=verdict,
                    llm_scores={**scores, "composite": composite},
                    llm_evidence=rationale)
            .on_conflict_do_update(
                constraint="uq_disruption_object_window",
                set_={
                    "llm_verdict": verdict,
                    "llm_scores": {**scores, "composite": composite},
                    "llm_evidence": rationale,
                    "updated_at": sa.func.now(),
                },
            )
        )
        judged += 1
    if judged:
        logger.info("rotolo_judged", count=judged)
    return judged


class DisruptionService:
    """编排:拉专利 → 组件/z/合分 → 落库 →(可选)LLM 漏斗。"""

    def __init__(self, db_connection_id: int | None = None) -> None:
        self._db_connection_id = (
            db_connection_id or settings.weak_signal.corpus_db_connection_id
        )

    async def compute(self, *, session: AsyncSession | None = None,
                      years_back: int | None = None,
                      llm: bool | None = None) -> dict:
        ds = settings.disruption
        es = settings.emergence
        years_back = years_back or es.years_back
        llm = ds.llm_enabled if llm is None else llm
        this_year = date.today().year

        own_session = session is None
        if own_session:
            ctx = get_session()
        else:
            from contextlib import nullcontext
            ctx = nullcontext(session)
        async with ctx as sess:
            conn_orm = await sess.get(DBConnectionORM, self._db_connection_id)
            if conn_orm is None:
                return {"status": "failed", "error": "db_connection_not_found"}
            dsn = resolve_dsn(conn_orm)
            rows = await asyncio.to_thread(
                _load_patent_rows, dsn, this_year - years_back, this_year,
                es.max_patent_rows,
            )
            comp_rows = build_components(rows, weights={
                "novelty_comb": ds.w_novelty_comb, "growth": ds.w_growth,
                "new_entrant": ds.w_new_entrant, "small_team": ds.w_small_team,
                "term_novelty": ds.w_term_novelty,
            })
            written = await persist_assessments(sess, comp_rows)
            judged = 0
            if llm:
                judged = await run_llm_funnel(
                    sess, comp_rows, top_n=ds.top_n_llm, runs=ds.llm_runs,
                )
            if own_session:
                await sess.commit()
            return {
                "status": "done", "patent_rows": len(rows),
                "objects": len(comp_rows), "written": written, "llm_judged": judged,
            }
