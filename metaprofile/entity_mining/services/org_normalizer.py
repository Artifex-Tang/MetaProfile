"""机构归一建议服务(Phase D1):ROR API 匹配 + 本地 org_profile 别名比对。

流程:ROR 匹配(ROR 匹配指南简化版) → 与 org_profile 现有名比对 →
只写 entity_resolution_suggestion(status=pending),不自动合并。
ROR API 不可达 → 跳过远端,仅本地比对。
"""
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.entity_mining.domain.orm_models import (
    EntityResolutionSuggestionORM,
)
from metaprofile.entity_mining.services.name_utils import clean_org_name, similarity
from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

_ROR_ENDPOINT = "https://api.ror.org/organizations"


async def ror_match(name: str, *, timeout: float = 8.0) -> dict | None:
    """ROR affiliation 模糊匹配 → {ror_id, name, score} | None。

    score = ROR chosen 标志(1.0)或 difflib 相似度兜底。
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                _ROR_ENDPOINT, params={"affiliation": name},
                headers={"User-Agent": "MetaProfile/1.0"},
            )
            r.raise_for_status()
            items = r.json().get("items") or []
    except Exception as exc:  # noqa: BLE001  网络不可达静默降级
        logger.info("ror_api_unavailable", error=str(exc))
        return None
    best: dict | None = None
    for it in items:
        org = it.get("organization") or {}
        cand_name = org.get("name") or ""
        score = 1.0 if it.get("chosen") else similarity(clean_org_name(name), cand_name)
        if best is None or score > best["score"]:
            best = {
                "ror_id": org.get("id"),
                "name": cand_name,
                "score": round(min(score, 1.0), 4),
                "country": (org.get("country") or {}).get("country_name"),
            }
    return best


async def _upsert_suggestion(session: AsyncSession, row: dict) -> None:
    stmt = pg_insert(EntityResolutionSuggestionORM).values(**row)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ers_entity_kind_name",
        set_={
            "matched_id": stmt.excluded.matched_id,
            "matched_name": stmt.excluded.matched_name,
            "score": stmt.excluded.score,
            "detail": stmt.excluded.detail,
        },
    )
    await session.execute(stmt)


class OrgNormalizerService:
    """distinct 机构名(Doris applicant top-N)→ ROR/本地匹配建议。"""

    def __init__(self, db_connection_id: int | None = None) -> None:
        self._db_connection_id = (
            db_connection_id or settings.weak_signal.corpus_db_connection_id
        )

    async def suggest(self, session: AsyncSession,
                      raw_names: list[str] | None = None,
                      *, use_ror: bool = True) -> dict:
        if raw_names is None:
            raw_names = await self._load_top_applicants()
        clean = {}
        for n in raw_names:
            c = clean_org_name(n)
            if len(c) >= 2:
                clean[n] = c
        profiles = (await session.execute(
            select(OrgProfileORM.org_id, OrgProfileORM.name_cn,
                   OrgProfileORM.name_en)
        )).all()
        written = 0
        for raw, cn in clean.items():
            # 本地精确/模糊比对(免网络)
            local_best = None
            for oid, name_cn, name_en in profiles:
                for pn in (name_cn, name_en):
                    if not pn:
                        continue
                    s = similarity(cn, clean_org_name(pn))
                    if s and (local_best is None or s > local_best["score"]):
                        local_best = {
                            "matched_id": oid, "matched_name": pn, "score": round(s, 4),
                        }
            detail: dict = {"clean_name": cn}
            matched = local_best
            if use_ror:
                remote = await ror_match(raw)
                if remote and (matched is None or remote["score"] > matched["score"]):
                    matched = {
                        "matched_id": remote["ror_id"],
                        "matched_name": remote["name"],
                        "score": remote["score"],
                    }
                    detail["ror"] = remote
            if matched and matched["score"] >= 0.75:
                await _upsert_suggestion(session, {
                    "entity_type": "org", "raw_name": raw,
                    "suggestion_kind": "ror_match",
                    "matched_id": matched["matched_id"],
                    "matched_name": matched["matched_name"],
                    "score": matched["score"], "detail": detail,
                })
                written += 1
        logger.info("org_normalize_suggested", written=written, names=len(clean))
        return {"status": "done", "names": len(clean), "suggestions": written}

    async def _load_top_applicants(self) -> list[str]:
        import pymysql

        from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
        from metaprofile.ingest_ods.services.connections import resolve_dsn
        from metaprofile.shared.db.postgres import get_session

        async with get_session() as s:
            conn_orm = await s.get(DBConnectionORM, self._db_connection_id)
            if conn_orm is None:
                return []
            dsn = resolve_dsn(conn_orm)
        es = settings.emergence

        def _q() -> list[str]:
            conn = pymysql.connect(**dsn)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT applicant, COUNT(*) c FROM ods_invention_patent_cn "
                    "WHERE applicant IS NOT NULL AND applicant != '' "
                    "GROUP BY applicant ORDER BY c DESC LIMIT %s",
                    (es.max_patent_rows // 100,),
                )
                rows = [r[0] for r in cur.fetchall()]
                cur.close()
                return rows
            finally:
                conn.close()

        return await asyncio.to_thread(_q)
