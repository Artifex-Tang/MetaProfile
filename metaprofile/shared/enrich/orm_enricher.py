"""直写 typed ORM 的 LLM 补全核心。

区别于 foundation/enrichment/pipeline（写 entity_store JSONB，UI 不读），
本模块面向 profile 层：对已存在的 typed ORM 行，用 LLM 填缺失字段、重算
completeness、刷新 data_as_of、写 EntityChangeLog(method=llm_enrich)。

复用 foundation/enrichment 的 completeness 评分 + LLMFieldFiller（不接 RAG，
context_docs 传空——按需补全以画像自身已知属性为上下文）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.foundation.enrichment.completeness import _FIELD_SPEC, score_completeness
from metaprofile.foundation.enrichment.llm_filler import LLMFieldFiller
from metaprofile.shared.db.orm_models import EntityChangeLogORM
from metaprofile.shared.schemas.base import EntityType, SourceMethod

logger = structlog.get_logger(__name__)


@dataclass
class EnrichOutcome:
    entity_id: str
    entity_type: EntityType
    completeness_before: float
    completeness_after: float
    filled_fields: list[str] = field(default_factory=list)
    skipped: bool = False
    error: str | None = None


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


async def enrich_one(
    *,
    session: AsyncSession,
    entity_type: EntityType,
    orm_cls: type,
    entity_id: str,
    filler: LLMFieldFiller,
    change_log_entity_type: str,
) -> EnrichOutcome:
    """对单个 typed ORM 行执行 LLM 补全（直写）。

    Args:
        session: 已开启的异步会话；函数内 commit。
        entity_type: 实体类型（驱动 _FIELD_SPEC）。
        orm_cls: typed ORM 类（主键 = entity_id）。
        entity_id: 实体主键值。
        filler: LLMFieldFiller 实例。
        change_log_entity_type: EntityChangeLogORM.entity_type 字段值（tech/org/...）。
    """
    orm = await session.get(orm_cls, entity_id)
    if orm is None:
        return EnrichOutcome(
            entity_id=entity_id, entity_type=entity_type,
            completeness_before=0.0, completeness_after=0.0,
            error="entity_not_found",
        )

    required, recommended = _FIELD_SPEC.get(entity_type, ([], []))
    all_fields = required + recommended
    attrs = {f: getattr(orm, f, None) for f in all_fields}
    before = score_completeness(entity_type, attrs)

    if not before.needs_enrichment:
        return EnrichOutcome(
            entity_id=entity_id, entity_type=entity_type,
            completeness_before=before.score, completeness_after=before.score,
            skipped=True,
        )

    fill = await filler.fill(
        entity_type=entity_type,
        entity_attrs=attrs,
        missing_fields=before.missing_fields,
        context_docs=[],
    )

    if not fill.filled_fields:
        logger.info("enrich_no_fill", entity_id=entity_id, before=before.score)
        return EnrichOutcome(
            entity_id=entity_id, entity_type=entity_type,
            completeness_before=before.score, completeness_after=before.score,
        )

    applied: dict[str, Any] = {}
    for fname, fval in fill.filled_fields.items():
        if fname in all_fields and _present(fval):
            setattr(orm, fname, fval)
            applied[fname] = fval

    if not applied:
        return EnrichOutcome(
            entity_id=entity_id, entity_type=entity_type,
            completeness_before=before.score, completeness_after=before.score,
        )

    new_attrs = {**attrs, **applied}
    after = score_completeness(entity_type, new_attrs)
    orm.completeness = after.score
    orm.data_as_of = date.today()

    session.add(EntityChangeLogORM(
        entity_id=entity_id,
        entity_type=change_log_entity_type,
        field=",".join(applied.keys()),
        old_value=None,
        new_value={"filled": applied},
        method=SourceMethod.LLM_ENRICH.value,
        changed_at=datetime.now(timezone.utc),
    ))
    await session.commit()

    logger.info(
        "enrich_done",
        entity_id=entity_id,
        entity_type=entity_type.value,
        before=before.score,
        after=after.score,
        filled=list(applied.keys()),
    )
    return EnrichOutcome(
        entity_id=entity_id, entity_type=entity_type,
        completeness_before=before.score, completeness_after=after.score,
        filled_fields=list(applied.keys()),
    )
