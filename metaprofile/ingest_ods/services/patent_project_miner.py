"""产业技术布局画像(A 方案,2026-10-15):从现有专利表挖掘"企业×技术域"攻关簇。

用户决策:project 画像重语义为产业技术布局——同申请人+同 IPC subclass 域的
专利簇 = 一个技术布局项目(名称=公司·技术域技术布局),零 LLM,真数据聚合。
替换 market(采购公告)→project 的旧语义 mapping。

纯函数 cluster_patents(可测)+ PatentProjectMiner(拉数/聚合/落库)。
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from collections import defaultdict
from datetime import UTC, date, datetime

import pymysql
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.shared.db.orm_models import EntityChangeLogORM

logger = structlog.get_logger(__name__)

_APP_SEP = re.compile(r"[;；,，|]")
_SUB_RE = re.compile(r"([A-H]\d{2}[A-Z])")


def _subclass(ipc_type: str | None) -> str:
    if not ipc_type:
        return ""
    m = _SUB_RE.search(str(ipc_type))
    return m.group(1) if m else ""


def cluster_patents(rows: list[tuple[str, str, int, str]],
                    *, min_patents: int = 5) -> list[dict]:
    """(申请人串, ipc_type, 年, 标题) 行 → 企业×技术域簇列表。

    申请人串多值(;)按每个申请人独立归簇;簇内专利数 ≥ min_patents 保留。
    """
    agg: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"n": 0, "years": set(), "titles": []},
    )
    for applicant, ipc_type, year, title in rows:
        sub = _subclass(ipc_type)
        if not sub:
            continue
        for app in _APP_SEP.split(applicant or ""):
            a = app.strip()
            if len(a) < 4:
                continue
            c = agg[(a, sub)]
            c["n"] += 1
            c["years"].add(int(year))
            if title:
                c["titles"].append(title)
    out = []
    for (applicant, sub), c in agg.items():
        if c["n"] < min_patents:
            continue
        out.append({
            "applicant": applicant,
            "ipc": sub,
            "patents": c["n"],
            "years": sorted(c["years"]),
            "sample_titles": c["titles"][:5],
        })
    out.sort(key=lambda x: -x["patents"])
    return out


def layout_id(applicant: str, ipc: str) -> str:
    return "pp:" + hashlib.md5(f"{applicant}|{ipc}".encode()).hexdigest()[:12]


def _is_active(years: list[int]) -> bool:
    return bool(years) and years[-1] >= date.today().year - 2


def build_profile_rows(clusters: list[dict], ipc_names: dict[str, str]) -> list[dict]:
    """簇 → project_profile 行值 dict(name_cn/main_orgs/tech_domain 等)。"""
    out = []
    for c in clusters:
        domain_cn = ipc_names.get(c["ipc"]) or c["ipc"]
        out.append({
            "project_id": layout_id(c["applicant"], c["ipc"]),
            "name_cn": [f"{c['applicant']}·{domain_cn}技术布局"],
            "name_en": [],
            "name_other": [],
            "tech_domain": [domain_cn],
            "sub_tech_domain": [],
            "main_orgs": [c["applicant"]],
            "undertaking_orgs": [],
            "undertaking_enterprises": [],
            "budget_activities": [],
            "progress": [],
            "managers": [],
            "research_content": [
                f"基于 {c['patents']} 件专利聚合({c['years'][0]}-{c['years'][-1]} 年),"
                f"IPC 域 {c['ipc']}"
            ],
            "start_date": date(c["years"][0], 1, 1),
            "finish_date": date(c["years"][-1], 12, 31),
            "status": "active" if _is_active(c["years"]) else "archived",
            # 重要度:专利量归一(列表 confidence 降序 → 技术布局排前,
            # 采购公告类旧数据 0.3 沉底,2026-10-15 用户决策)
            "confidence": round(0.7 + min(c["patents"] / 50, 0.25), 4),
            "_sample_titles": c["sample_titles"],
        })
    return out


def _load_patent_rows(dsn: dict, limit: int) -> list[tuple[str, str, int, str]]:
    conn = pymysql.connect(**{**dsn, "charset": "utf8mb4"})
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        cur.execute(
            "SELECT applicant, ipc_type, YEAR(filing_date), title "
            "FROM ods_invention_patent_cn "
            "WHERE ipc_type IS NOT NULL AND ipc_type != '' "
            "AND applicant IS NOT NULL AND applicant != '' "
            "AND filing_date >= '2015-01-01' "
            "ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        rows = [(str(a or ""), str(i or ""), int(y), str(t or ""))
                for a, i, y, t in cur.fetchall() if y]
        cur.close()
        return rows
    finally:
        conn.close()


async def upsert_layouts(session: AsyncSession, rows: list[dict]) -> int:
    """project_profile upsert(幂等 pp: id)+ change_log 审计。"""
    now = datetime.now(UTC)
    written = 0
    for r in rows:
        titles = r.pop("_sample_titles", [])
        orm = await session.get(ProjectProfileORM, r["project_id"])
        if orm is None:
            session.add(ProjectProfileORM(**r))
            session.add(EntityChangeLogORM(
                entity_id=r["project_id"], entity_type="project", field="*",
                old_value=None,
                new_value={"action": "patent_layout_create",
                           "sample_titles": titles[:3]},
                method="rule_extract", changed_at=now,
            ))
        else:
            for k, v in r.items():
                if k != "project_id":
                    setattr(orm, k, v)
        written += 1
        if written % 1000 == 0:
            await session.flush()
    await session.flush()
    return written


class PatentProjectMiner:
    """编排:Doris 专利 → 簇聚合 → project_profile。"""

    def __init__(self, db_connection_id: int | None = None) -> None:
        from metaprofile.shared.config.settings import settings
        self._db_connection_id = (
            db_connection_id or settings.weak_signal.corpus_db_connection_id
        )

    async def mine(self, session: AsyncSession, *, min_patents: int = 5,
                   max_rows: int = 300000) -> dict:
        from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
        from metaprofile.ingest_ods.services.connections import resolve_dsn
        from metaprofile.profile_tech.domain.orm_models import TechProfileORM

        conn_orm = await session.get(DBConnectionORM, self._db_connection_id)
        if conn_orm is None:
            return {"status": "failed", "error": "db_connection_not_found"}
        dsn = resolve_dsn(conn_orm)
        rows = await asyncio.to_thread(_load_patent_rows, dsn, max_rows)
        clusters = cluster_patents(rows, min_patents=min_patents)
        ipc_names = {t.ipc_code: t.tech_name_cn
                     for t in (await session.execute(
                         select(TechProfileORM)
                         .where(TechProfileORM.tech_layer == "DOMAIN")
                     )).scalars().all() if t.ipc_code}
        profile_rows = build_profile_rows(clusters, ipc_names)
        written = await upsert_layouts(session, profile_rows)
        logger.info("patent_layouts_mined", clusters=len(clusters), written=written)
        return {"status": "done", "patent_rows": len(rows),
                "clusters": len(clusters), "written": written}
