"""项目 LLM 分类(Phase D3):project_profile → L1 IPC 域零样本。

标签集 = tech_emergence_indicator 按专利量 top-N 的 ipc: 域(+ipc 字典中文名)。
批处理(每批 ≤20 项目一次调用省配额)→ 写 project_profile.tech_domain +
建议行留档。LLM 失败 → 跳过该批,不阻塞。
"""
from __future__ import annotations

import structlog
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.entity_mining.domain.orm_models import (
    EntityResolutionSuggestionORM,
)
from metaprofile.ingest_ods.domain.ipc_taxonomy import name_of
from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import ProfileBase

logger = structlog.get_logger(__name__)


class ProjectDomainAssignment(ProfileBase):
    project_id: str = Field(..., description="project_profile 主键")
    domain_code: str = Field(..., description="IPC subclass 码,如 G06T")
    domain_name: str = Field(..., description="域中文名")
    confidence: float = Field(..., ge=0.0, le=1.0)


class ProjectDomainBatch(ProfileBase):
    assignments: list[ProjectDomainAssignment] = Field(default_factory=list)


SYSTEM_PROMPT = """你是科研项目分类专家。把每个项目归入一个 IPC 技术域(从给定标签集选)。
规则:只从标签集选;最贴切的单域;不确定 confidence 降低。"""


async def load_label_set(session: AsyncSession, *, top_n: int = 100) -> list[dict]:
    """top-N IPC 域标签(专利量降序,取中文名)。"""
    from metaprofile.new_tech_discovery.domain.orm_models import (
        TechEmergenceIndicatorORM,
    )

    rows = (await session.execute(
        select(
            TechEmergenceIndicatorORM.object_id,
            TechEmergenceIndicatorORM.metrics,
        ).where(
            TechEmergenceIndicatorORM.object_type == "ipc_domain",
        ).order_by(
            TechEmergenceIndicatorORM.window_month.desc()
        ).limit(2000)
    )).all()
    ranked = sorted(
        rows, key=lambda r: -int((r.metrics or {}).get("patents", 0)),
    )[:top_n]
    out = []
    for object_id, _m in ranked:
        code = object_id.split(":", 1)[-1]
        out.append({"code": code, "name": name_of(code) or code})
    return out


def _first(v) -> str:
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def _build_prompt(projects: list, labels: list[dict]) -> str:
    label_txt = "\n".join(f"- {l['code']} {l['name']}" for l in labels)
    proj_txt = "\n".join(
        f"- id={p.project_id} 名称={_first(p.name_cn) or _first(p.name_en) or p.project_id} "
        f"内容={_first(p.research_content)[:120]}"
        for p in projects
    )
    return f"""标签集(IPC 域):
{label_txt}

项目列表:
{proj_txt}

请为每个项目输出分类(classify_projects 函数)。"""


async def classify_projects(session: AsyncSession, *, batch_size: int = 20,
                            max_projects: int = 50) -> dict:
    """未分类项目 → LLM 批分类 → 写 tech_domain + 建议留档。"""
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from metaprofile.shared.llm.function_calling import call_with_schema
    from metaprofile.shared.llm.gateway import LLMGateway

    unclassified = (await session.execute(
        select(ProjectProfileORM)
        .where(func.json_array_length(ProjectProfileORM.tech_domain) == 0)
        .limit(max_projects)
    )).scalars().all()
    if not unclassified:
        return {"status": "done", "classified": 0}

    labels = await load_label_set(session)
    if not labels:
        return {"status": "failed", "error": "empty_label_set"}

    gateway = LLMGateway()
    classified = 0
    for start in range(0, len(unclassified), batch_size):
        batch = unclassified[start:start + batch_size]
        try:
            result, _ = await call_with_schema(
                gateway=gateway, model=settings.llm.agent_model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=_build_prompt(batch, labels),
                function_name="classify_projects",
                function_description="为科研项目列表分配 IPC 技术域",
                output_schema=ProjectDomainBatch,
                caller="entity_mining.project_classify",
            )
        except Exception as exc:  # noqa: BLE001  LLM 失败跳批
            logger.warning("project_classify_failed", error=str(exc))
            continue
        by_id = {a.project_id: a for a in result.assignments}
        for p in batch:
            a = by_id.get(p.project_id)
            if a is None:
                continue
            p.tech_domain = [a.domain_name]
            stmt = pg_insert(EntityResolutionSuggestionORM).values(
                entity_type="project",
                raw_name=p.project_id,
                suggestion_kind="project_classify",
                matched_id=f"ipc:{a.domain_code}",
                matched_name=a.domain_name, score=a.confidence,
                detail={},
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_ers_entity_kind_name",
                set_={"matched_id": stmt.excluded.matched_id,
                      "matched_name": stmt.excluded.matched_name,
                      "score": stmt.excluded.score},
            )
            await session.execute(stmt)
            classified += 1
    logger.info("projects_classified", classified=classified)
    return {"status": "done", "classified": classified, "labels": len(labels)}
