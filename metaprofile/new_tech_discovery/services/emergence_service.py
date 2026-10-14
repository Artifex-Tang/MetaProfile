"""新兴指标计算服务(Phase B5):Doris 专利 → 域/对指标 → tech_emergence_indicator。

数据路径:
1. 拉 ODS 专利(filing_date 年窗,applicant+ipc_type,cap max_patent_rows)
2. 域级:逐年 patents/applicant 集合 → Porter(活跃/新进入者/DT)+ Haupt 比
   + S 曲线阶段(累计)+ TEM 象限(份额=域专利/总专利,增速=份额环比)
3. 对级:多 IPC 专利 → 逐年 Salton 共类强度 → emerging_pairs(新对+升)
4. 全量 upsert tech_emergence_indicator(窗口=年,window_month=当年 1 月 1 日)

零 LLM;重计算在 Doris 拉数侧只做一次全表扫描(cap 保护)。
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
from metaprofile.new_tech_discovery.domain.orm_models import (
    TechEmergenceIndicatorORM,
)
from metaprofile.new_tech_discovery.services.emergence_metrics import (
    doubling_time,
    emerging_pairs,
    haupt_ratio,
    pair_combinations,
    porter_indicators,
    s_curve_stage,
    tem_quadrants,
)
from metaprofile.shared.config.settings import settings
from metaprofile.shared.db.postgres import get_session

logger = structlog.get_logger(__name__)

# subclass 提取复用 ipc_taxonomy 语义:首个 A-H##X 段
_SUB_RE = re.compile(r"([A-H]\d{2}[A-Z])")
_SEP_RE = re.compile(r"[;,，；\s]+")


def subclasses_of(ipc_type: str | None) -> list[str]:
    """ipc_type 串(G06T7/73(2017.01)I[,; ]…) → 去重 subclass 列表。"""
    if not ipc_type:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for part in _SEP_RE.split(str(ipc_type)):
        m = _SUB_RE.search(part)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def _load_patent_rows(dsn: dict, year_from: int, year_to: int,
                      limit: int) -> list[tuple[int, str, str]]:
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        cur.execute(
            "SELECT YEAR(filing_date), applicant, ipc_type "
            "FROM ods_invention_patent_cn "
            "WHERE filing_date IS NOT NULL AND filing_date >= %s "
            "AND filing_date < %s AND ipc_type IS NOT NULL AND ipc_type != '' "
            "ORDER BY id DESC LIMIT %s",  # 取最新(cap 截旧不截新)
            (f"{year_from}-01-01", f"{year_to + 1}-01-01", limit),
        )
        rows = [
            (int(y), str(a or ""), str(i or ""))
            for y, a, i in cur.fetchall()
            if y is not None
        ]
        cur.close()
        return rows
    finally:
        conn.close()


def build_domain_rows(rows: list[tuple[int, str, str]]) -> list[dict]:
    """专利行 → 每 IPC 域每年指标行(含 TEM 象限与 S 曲线阶段)。"""
    years = sorted({y for y, _, _ in rows})
    if not years:
        return []
    # 域 × 年 → 专利数 / 申请人集合
    dom_pat: dict[str, dict[int, int]] = {}
    dom_app: dict[str, dict[int, set[str]]] = {}
    year_total: dict[int, int] = {}
    for y, applicant, ipc_type in rows:
        subs = subclasses_of(ipc_type)
        apps = {a.strip() for a in re.split(r"[;；,，|]", applicant) if a.strip()}
        for sub in subs[:1]:  # 域归属取首个 subclass(与 L1 冷启动一致)
            dom_pat.setdefault(sub, {}).setdefault(y, 0)
            dom_pat[sub][y] += 1
            dom_app.setdefault(sub, {}).setdefault(y, set())
            dom_app[sub][y] |= apps
            year_total[y] = year_total.get(y, 0) + 1

    # TEM:份额(域专利/当年总专利)与增速
    shares_last: dict[str, float] = {}
    growths: dict[str, float] = {}
    for sub, by_year in dom_pat.items():
        series = [by_year.get(y, 0) for y in years]
        tot = [max(year_total.get(y, 0), 1) for y in years]
        share_series = [p / t for p, t in zip(series, tot, strict=True)]
        shares_last[sub] = share_series[-1]
        growths[sub] = (
            share_series[-1] / share_series[-2] - 1
            if len(share_series) >= 2 and share_series[-2] > 0 else 0.0
        )
    quadrants = tem_quadrants(shares_last, growths)
    last_year = years[-1]

    out: list[dict] = []
    for sub, by_year in dom_pat.items():
        ents_by_year = [dom_app.get(sub, {}).get(y, set()) for y in years]
        porter = porter_indicators(ents_by_year)
        series = [by_year.get(y, 0) for y in years]
        applicants = [len(e) for e in ents_by_year]
        cum = []
        run = 0
        for v in series:
            run += v
            cum.append(float(run))
        stage = s_curve_stage([float(i) for i in range(len(series))], cum)
        prev_p = series[-2] if len(series) >= 2 else 0
        out.append({
            "object_type": "ipc_domain",
            "object_id": f"ipc:{sub}",
            "window_month": date(last_year, 1, 1),
            "metrics": {
                "patents": series[-1],
                "applicants": applicants[-1],
                "active_entities": porter[-1]["active_entities"],
                "new_entrant_ratio": round(porter[-1]["new_entrant_ratio"], 4),
                "doubling_time": doubling_time(prev_p, series[-1]),
                "tem_share": round(shares_last[sub], 6),
                "tem_growth": round(growths[sub], 4),
                "tem_quadrant": quadrants[sub],
                "s_curve_stage": stage,
                "haupt_ratio": haupt_ratio(series[-3:], applicants[-3:]),
            },
        })
    return out


def build_pair_rows(rows: list[tuple[int, str, str]], *,
                    lookback_years: int = 3,
                    min_salton: float = 0.05) -> list[dict]:
    """专利行 → 最新年新兴跨域对指标行。"""
    years = sorted({y for y, _, _ in rows})
    if not years:
        return []
    pairs_by_win: dict[int, dict[tuple[str, str], int]] = {}
    domain_counts: dict[int, dict[str, int]] = {}
    for y, _applicant, ipc_type in rows:
        subs = set(subclasses_of(ipc_type))
        for sub in subs:
            domain_counts.setdefault(y, {})
            domain_counts[y][sub] = domain_counts[y].get(sub, 0) + 1
        for pair in pair_combinations(subs):
            pairs_by_win.setdefault(y, {})
            pairs_by_win[y][pair] = pairs_by_win[y].get(pair, 0) + 1
    last_year = years[-1]
    return [
        {
            "object_type": "ipc_pair",
            "object_id": p["object_id"],
            "window_month": date(last_year, 1, 1),
            "metrics": {
                "count": p["count"],
                "salton": round(p["salton"], 6),
                "first_seen": p["first_seen"],
                "is_new_pair": p["is_new_pair"],
                "salton_rising": p["salton_rising"],
            },
        }
        for p in emerging_pairs(
            pairs_by_win, domain_counts,
            lookback_years=lookback_years, min_salton=min_salton,
        )
    ]


async def persist_indicators(session: AsyncSession, rows: list[dict]) -> int:
    """批量 upsert(ON CONFLICT 对象×窗口 DO UPDATE metrics)。"""
    written = 0
    for start in range(0, len(rows), 500):
        chunk = rows[start:start + 500]
        stmt = pg_insert(TechEmergenceIndicatorORM).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_emergence_object_window",
            set_={
                "metrics": stmt.excluded.metrics,
                "updated_at": sa.func.now(),
            },
        )
        await session.execute(stmt)
        written += len(chunk)
    if written:
        logger.info("emergence_indicators_persisted", rows=written)
    return written


class EmergenceService:
    """编排:拉专利 → 域/对指标 → upsert。"""

    def __init__(self, db_connection_id: int | None = None) -> None:
        self._db_connection_id = (
            db_connection_id or settings.weak_signal.corpus_db_connection_id
        )

    async def compute(self, *, session: AsyncSession | None = None,
                      years_back: int | None = None) -> dict:
        es = settings.emergence
        years_back = years_back or es.years_back
        this_year = date.today().year
        year_from = this_year - years_back

        own_session = session is None
        if own_session:
            ctx = get_session()
        else:
            from contextlib import nullcontext
            ctx = nullcontext(session)
        async with ctx as sess:
            conn_orm = await sess.get(DBConnectionORM, self._db_connection_id)
            if conn_orm is None:
                logger.warning("emergence_no_db_connection", id=self._db_connection_id)
                return {"status": "failed", "error": "db_connection_not_found"}
            dsn = resolve_dsn(conn_orm)
            rows = await asyncio.to_thread(
                _load_patent_rows, dsn, year_from, this_year, es.max_patent_rows,
            )
            domain_rows = build_domain_rows(rows)
            pair_rows = build_pair_rows(
                rows, lookback_years=es.pair_lookback_years,
                min_salton=es.pair_min_salton,
            )
            all_rows = domain_rows + pair_rows
            written = await persist_indicators(sess, all_rows)
            if own_session:
                await sess.commit()
            return {
                "status": "done", "patent_rows": len(rows),
                "domain_objects": len(domain_rows), "pair_objects": len(pair_rows),
                "written": written,
            }
