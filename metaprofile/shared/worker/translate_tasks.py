"""翻译 celery 任务：单条 + 批量。

run_async 复用 worker 持久 loop（非 asyncio.run，避免 asyncpg 跨任务 loop bug）。
"""
from __future__ import annotations

import structlog
from typing import Any

from sqlalchemy import or_, select

from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.enrich.translator import NAME_FIELDS, TranslateOutcome, _orm_cls, translate_name_one
from metaprofile.shared.worker.async_runner import run_async
from metaprofile.shared.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)

_ID_COL = {"tech": "tech_id", "org": "org_id", "person": "person_id", "project": "project_id"}


async def _async_translate_name(entity_type: str, entity_id: str) -> dict[str, Any]:
    try:
        async with get_session() as session:
            out: TranslateOutcome = await translate_name_one(session, entity_type, entity_id)
            return {
                "status": "done" if out.translated else "skipped",
                "translated": out.translated, "new_value": out.new_value,
                "reason": out.reason, "error": out.error,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("translate_name_failed", entity_id=entity_id, error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.translate.name", bind=True)
def translate_name(self, entity_type: str, entity_id: str) -> dict[str, Any]:
    return run_async(_async_translate_name(entity_type, entity_id))


async def _scan_untranslated(entity_type: str | None) -> list[tuple[str, str]]:
    """扫 name_cn 空 & name_en 非空的实体 id（单类型上限 5000 防过载）。"""
    out: list[tuple[str, str]] = []
    types = [entity_type] if entity_type else list(NAME_FIELDS.keys())
    async with get_session() as session:
        for t in types:
            cn_field, en_field = NAME_FIELDS[t]
            orm_cls = _orm_cls(t)
            cn_col = getattr(orm_cls, cn_field)
            en_col = getattr(orm_cls, en_field)
            id_col = getattr(orm_cls, _ID_COL[t])
            rows = (await session.execute(
                select(id_col).where(
                    or_(cn_col.is_(None), cn_col == ""),
                    en_col.isnot(None), en_col != "",
                )
            )).scalars().all()
            out.extend([(t, str(r)) for r in rows[:5000]])
    return out


async def _async_batch(entity_type: str | None) -> dict[str, Any]:
    translated = skipped = failed = 0
    try:
        targets = await _scan_untranslated(entity_type)
        for t, eid in targets:
            # 每条独立 session，避免长事务
            async with get_session() as s:
                out = await translate_name_one(s, t, eid)
            if out.translated:
                translated += 1
            elif out.error:
                failed += 1
            else:
                skipped += 1
        return {"status": "done", "translated": translated, "skipped": skipped, "failed": failed}
    except Exception as exc:  # noqa: BLE001
        logger.warning("translate_batch_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.translate.batch", bind=True)
def batch_translate_names(self, entity_type: str | None = None) -> dict[str, Any]:
    return run_async(_async_batch(entity_type))
