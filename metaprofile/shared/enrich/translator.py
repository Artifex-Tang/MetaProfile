"""en→cn 名称翻译：name_cn 空 & name_en 有 → LLM 译 → 写 name_cn + EntityChangeLog。

复用 LLMGateway.complete（纯文本出）+ EntityChangeLogORM（method=llm_translate）。
失败不写 name_cn（不污染）。project name_cn/name_en 是 list → 取/写 [0]/[译值]。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.shared.db.orm_models import EntityChangeLogORM
from metaprofile.shared.llm.gateway import LLMGateway

logger = structlog.get_logger(__name__)

# entity_type → (name_cn 字段, name_en 字段)
NAME_FIELDS: dict[str, tuple[str, str]] = {
    "tech": ("tech_name_cn", "tech_name_en"),
    "org": ("name_cn", "name_en"),
    "person": ("name_cn", "name_en"),
    "project": ("name_cn", "name_en"),
}

_SYSTEM_PROMPT = (
    "你是科技术语翻译器。把英文技术/机构/人名译为中文专业术语，"
    "只输出译文一行，禁音译加注、禁解释、禁标点。"
)


def _orm_cls(entity_type: str):
    """entity_type → ORM 类（延迟 import 避免循环）。"""
    from metaprofile.profile_tech.domain.orm_models import TechProfileORM
    from metaprofile.profile_org.domain.orm_models import OrgProfileORM
    from metaprofile.profile_person.domain.orm_models import PersonProfileORM
    from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
    return {
        "tech": TechProfileORM, "org": OrgProfileORM,
        "person": PersonProfileORM, "project": ProjectProfileORM,
    }[entity_type]


def _scalar(v: Any) -> str:
    """list（project）取 [0]；None/空 → ''。"""
    if isinstance(v, list):
        v = v[0] if v else ""
    return str(v).strip() if v else ""


@dataclass
class TranslateOutcome:
    translated: bool
    reason: str = ""
    new_value: str | None = None
    error: str | None = None


async def translate_name_one(
    db: AsyncSession, entity_type: str, entity_id: str, *, gateway: LLMGateway | None = None,
) -> TranslateOutcome:
    if entity_type not in NAME_FIELDS:
        return TranslateOutcome(False, reason="unknown_type")
    cn_field, en_field = NAME_FIELDS[entity_type]
    orm = await db.get(_orm_cls(entity_type), entity_id)
    if orm is None:
        return TranslateOutcome(False, reason="not_found")

    cn = _scalar(getattr(orm, cn_field, ""))
    en = _scalar(getattr(orm, en_field, ""))
    if cn:
        return TranslateOutcome(False, reason="name_cn_present")
    if not en:
        return TranslateOutcome(False, reason="no_source")

    gw = gateway or LLMGateway()
    try:
        resp = await gw.complete(messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": en},
        ])
        translated = (resp.content or "").strip().splitlines()[0].strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("translate_llm_failed", entity_id=entity_id, error=str(exc))
        return TranslateOutcome(False, error=str(exc))
    if not translated:
        return TranslateOutcome(False, error="empty_translation")

    # project name_cn 是 list → 包一层
    new_val: Any = [translated] if entity_type == "project" else translated
    setattr(orm, cn_field, new_val)
    db.add(EntityChangeLogORM(
        entity_id=entity_id, entity_type=entity_type, field=cn_field,
        old_value=None, new_value={"name_cn": translated},
        method="llm_translate", operator=None, source_doc_id=None,
        reason=f"en→cn translate: {en}", changed_at=datetime.now(timezone.utc),
    ))
    await db.flush()
    return TranslateOutcome(True, new_value=translated)
