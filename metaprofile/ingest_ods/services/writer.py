"""阶段⑤ 写入：profile 主表 upsert + 评分列 + 变更日志；关系→TripleWriter→Neo4j。"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.foundation.relation.triple_writer import TripleWriter
from metaprofile.ingest_ods.domain.orm_models import IngestErrorORM
from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_person.domain.orm_models import PersonProfileORM
from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.shared.db.orm_models import EntityChangeLogORM
from metaprofile.shared.schemas.base import EntityType

logger = structlog.get_logger(__name__)

# profile_type → (ORM, id 列属性名)
_PROFILE_TABLES = {
    "tech": (TechProfileORM, "tech_id"),
    "org": (OrgProfileORM, "org_id"),
    "person": (PersonProfileORM, "person_id"),
    "project": (ProjectProfileORM, "project_id"),
}

# 各 profile 主表 NOT NULL-no-default 列的占位（避免 insert 约束失败）。
# 已对照各 ORM 的 mapped_column(nullable=False) 且无 Python default 的列核对：
#   - tech: tech_name_cn/tech_name_en/tech_domain/tech_summary/current_status/trend
#   - org:  name_cn/name_en/country/summary/org_types/nature/function/tech_domains
#   - person: name_cn/name_en/gender/nationality/summary/current_position/professional_domains
#   - project: name_cn/name_en/tech_domain/start_date/project_no/main_orgs/research_content/progress
_DEFAULTS = {
    "tech": {"tech_name_cn": "", "tech_name_en": "", "tech_domain": [], "tech_summary": "",
             "current_status": "", "trend": ""},
    "org": {"name_cn": "", "name_en": "", "country": "", "summary": "",
            "org_types": [], "nature": "", "function": "", "tech_domains": []},
    "person": {"name_cn": "", "name_en": "", "gender": "", "nationality": "", "summary": "",
               "current_position": [], "professional_domains": []},
    "project": {"name_cn": [], "name_en": [], "tech_domain": [],
                "start_date": None, "project_no": 0,
                "main_orgs": [], "research_content": [], "progress": []},
}


class Writer:
    """阶段⑤ 写入器：profile 主表 upsert + 评分 + 变更日志 + 关系。"""

    def __init__(
        self,
        triple_writer: TripleWriter | None = None,
        neo4j_repo: object | None = None,
    ) -> None:
        self._tw = triple_writer
        # FoundationNeo4jRepo,用于把 profile 节点写入 Neo4j(entity_id=PK),
        # 让 OrgRelationService 等 relation service 能按 PK 查到 ingest 创建的 profile。
        self._neo4j = neo4j_repo

    async def upsert_profile_node(
        self,
        *,
        entity_type: EntityType,
        entity_id: str,
        attrs: dict,
    ) -> None:
        """把 profile 节点写入 Neo4j(entity_id=PK),让 relation service 查得到。

        无 neo4j_repo(collector 未注入)时静默跳过 —— 保持向后兼容与单测便利。
        """
        if self._neo4j is None:
            return
        name = attrs.get("name_cn") or attrs.get("tech_name_cn")
        if isinstance(name, list):
            name = name[0] if name else None
        props: dict = {"name_cn": name or "", "entity_type": entity_type.value}
        # 补其他有用展示字段(非空)
        for k in ("summary", "tech_summary"):
            v = attrs.get(k)
            if v:
                props[k] = v
        await self._neo4j.upsert_entity_node(entity_type, entity_id, props)

    async def write_profile(
        self,
        session: AsyncSession,
        *,
        profile_type: str,
        entity_id: str,
        attrs: dict,
        scores: dict,
        method: str,
    ) -> str:
        orm_cls, id_col = _PROFILE_TABLES[profile_type]
        stmt = select(orm_cls).where(getattr(orm_cls, id_col) == entity_id)
        orm = (await session.execute(stmt)).scalar_one_or_none()

        merged = dict(_DEFAULTS.get(profile_type, {}))
        merged.update({k: v for k, v in attrs.items() if v not in (None, "", [])})
        merged["veracity_score"] = scores.get("veracity_score", 0.0)
        merged["timeliness_score"] = scores.get("timeliness_score", 0.0)
        merged["data_as_of"] = scores.get("data_as_of")

        now = datetime.now(timezone.utc)
        if orm is None:
            merged[id_col] = entity_id
            orm = orm_cls(**merged)
            session.add(orm)
            session.add(EntityChangeLogORM(
                entity_id=entity_id, entity_type=profile_type, field="*",
                old_value=None, new_value={"action": "ingest_create"},
                method=method, changed_at=now,
            ))
            action = "create"
        else:
            # I1: capture pre-update values BEFORE mutating
            pre = {k: getattr(orm, k, None) for k in merged if k != id_col}
            # I3: only mutate + log fields that actually changed
            changed = {
                k: v for k, v in merged.items()
                if k != id_col and pre.get(k) != v
            }
            for k, v in changed.items():
                setattr(orm, k, v)
            if changed:
                session.add(EntityChangeLogORM(
                    entity_id=entity_id, entity_type=profile_type, field="*",
                    old_value={k: pre[k] for k in changed},
                    new_value={"action": "ingest_update", "fields": changed},
                    method=method, changed_at=now,
                ))
            action = "update"
        await session.flush()
        logger.info(
            "profile_upserted",
            profile_type=profile_type,
            entity_id=entity_id,
            action=action,
        )
        return entity_id

    async def write_relations(self, triples: list) -> None:
        if not triples or self._tw is None:
            return
        await self._tw.write_batch(triples)

    async def record_error(self, session: AsyncSession, *, batch_id: int,
                           stage: str, error_msg: str,
                           source_table: str | None = None,
                           source_id: str | None = None) -> None:
        session.add(IngestErrorORM(batch_id=batch_id, source_table=source_table,
                                   source_id=source_id, stage=stage, error_msg=error_msg[:1000]))
        await session.flush()
