"""语料实体串 → 画像表 id 解析(Phase A4)。

信号语料里的实体(applicant/purchaser/keyword 等)与画像表 name 精确匹配
(IN 查询,过短/空名过滤)。匹配不到不勉强(返回子集)——模糊归一属 Phase D
ROR 工作,此处只做确定性链接。
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_person.domain.orm_models import PersonProfileORM
from metaprofile.profile_tech.domain.orm_models import TechProfileORM

_MIN_NAME_LEN = 2


def _clean_names(names: list[str], *, cap: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        s = str(n).strip()
        if len(s) >= _MIN_NAME_LEN and s not in seen:
            seen.add(s)
            out.append(s)
            if len(out) >= cap:
                break
    return out


class EntityLinker:
    """信号相关实体 → org/person/tech 画像 id。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _query_ids(self, orm, name_cols, id_col, names: list[str],
                         cap: int) -> list[str]:
        if not names:
            return []
        conds = [c.in_(names) for c in name_cols]
        rows = (
            await self._db.execute(
                select(id_col).where(or_(*conds)).order_by(id_col)
            )
        ).scalars().all()
        ids: list[str] = []
        seen: set[str] = set()
        for rid in rows:
            s = str(rid)
            if s not in seen:
                seen.add(s)
                ids.append(s)
                if len(ids) >= cap:
                    break
        return ids

    async def link_orgs(self, names: list[str], *, cap: int = 10) -> list[str]:
        clean = _clean_names(names, cap=50)
        return await self._query_ids(
            OrgProfileORM,
            [OrgProfileORM.name_cn, OrgProfileORM.name_en],
            OrgProfileORM.org_id, clean, cap,
        )

    async def link_persons(self, names: list[str], *, cap: int = 10) -> list[str]:
        clean = _clean_names(names, cap=50)
        return await self._query_ids(
            PersonProfileORM,
            [PersonProfileORM.name_cn, PersonProfileORM.name_en],
            PersonProfileORM.person_id, clean, cap,
        )

    async def link_techs(self, terms: list[str], *, cap: int = 10) -> list[str]:
        clean = _clean_names(terms, cap=50)
        return await self._query_ids(
            TechProfileORM,
            [TechProfileORM.tech_name_cn, TechProfileORM.tech_name_en],
            TechProfileORM.tech_id, clean, cap,
        )
