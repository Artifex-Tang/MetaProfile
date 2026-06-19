"""
MetaProfile 复合后端入口（单镜像、单进程承载全部后端功能）。

将四个画像服务（profile_tech / project / org / person）、三个分析层服务
（scan_monitor / new_tech_discovery / topic_selection）与设置服务（settings_api）
的全部路由聚合到一个 FastAPI 应用中。

各服务的路由路径本就不冲突：
- 画像层：/api/v1/profile/{tech|org|person|project}/...、/api/v1/stats/{type}、
           /api/v1/relation/{type}/...
- 分析层：/api/v1/frontier-tech/...、/api/v1/new-tech/...、/api/v1/topics/...
- 设置层：/api/v1/settings/...

nginx 的 /api-* 反代前缀被剥离后，全部落到本应用的 /api/v1 路由空间，
前端 client.ts 零改动。

启动：
    uvicorn metaprofile.backend.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from metaprofile.profile_org.api import (
    routes_enrichment as org_enrich,
    routes_mutation as org_mut,
    routes_query as org_query,
    routes_relation as org_relation,
    routes_stats as org_stats,
)
from metaprofile.profile_person.api import (
    routes_enrichment as person_enrich,
    routes_mutation as person_mut,
    routes_query as person_query,
    routes_relation as person_relation,
    routes_stats as person_stats,
)
from metaprofile.profile_project.api import (
    routes_enrichment as project_enrich,
    routes_mutation as project_mut,
    routes_query as project_query,
    routes_relation as project_relation,
    routes_stats as project_stats,
)
from metaprofile.profile_tech.api import (
    routes_enrichment as tech_enrich,
    routes_mutation as tech_mut,
    routes_query as tech_query,
    routes_relation as tech_relation,
    routes_stats as tech_stats,
)
from metaprofile.scan_monitor.api import routes_alert, routes_frontier
from metaprofile.new_tech_discovery.api import routes_new_tech, routes_signals
from metaprofile.topic_selection.api import routes_feedback, routes_topics
from metaprofile.settings_api.api.routes_collection import router as col_router
from metaprofile.settings_api.api.routes_datasource import router as ds_router
from metaprofile.settings_api.api.routes_db_connections import router as dbc_router
from metaprofile.settings_api.api.routes_llm import router as llm_router
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

PREFIX = settings.api_prefix  # /api/v1


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("metaprofile_backend_starting", env=settings.env, prefix=PREFIX)
    await _recover_orphan_collection_tasks()
    yield
    logger.info("metaprofile_backend_stopping")


async def _recover_orphan_collection_tasks() -> None:
    """startup 把上次进程中断遗留的 pending/running 采集任务标 failed（免 UI 永久卡 pending）。

    asyncio 采集任务随进程死亡而消失，status 不会回写；重启后这些记录将永远停在 pending/running。
    启动时一次性清扫为 failed。失败不阻断启动（DB 未就绪等情况）。
    """
    from sqlalchemy import update

    from metaprofile.settings_api.domain.orm_models import CollectionTaskORM
    from metaprofile.shared.db.postgres import get_session

    try:
        async with get_session() as session:
            res = await session.execute(
                update(CollectionTaskORM)
                .where(CollectionTaskORM.status.in_(("pending", "running")))
                .values(status="failed", error_msg="进程重启，任务中断（已自动标记失败）")
            )
            await session.commit()
            count = getattr(res, "rowcount", 0)
            if count:
                logger.info("orphan_collection_tasks_recovered", count=count)
    except Exception as e:  # noqa: BLE001 — 启动恢复失败不应阻断应用启动
        logger.warning("orphan_collection_tasks_recover_failed", error=str(e))


app = FastAPI(
    title="MetaProfile 产业技术情报系统（复合后端）",
    description="聚合四画像 + 三分析层 + 设置服务的全部 REST 接口。",
    version="1.0.0",
    lifespan=lifespan,
)

# ── 画像层（router 无前缀，统一挂 /api/v1） ──
for r in (tech_query, tech_mut, tech_relation, tech_stats, tech_enrich):
    app.include_router(r.router, prefix=PREFIX, tags=["profile_tech"])
for r in (project_query, project_mut, project_relation, project_stats, project_enrich):
    app.include_router(r.router, prefix=PREFIX, tags=["profile_project"])
for r in (org_query, org_mut, org_relation, org_stats, org_enrich):
    app.include_router(r.router, prefix=PREFIX, tags=["profile_org"])
for r in (person_query, person_mut, person_relation, person_stats, person_enrich):
    app.include_router(r.router, prefix=PREFIX, tags=["profile_person"])

# ── 分析层 ──
# 注意：alerts 的静态路径必须先于 frontier 的 {tech_id} 动态路径注册，
# 否则 /frontier-tech/alerts 会被 /frontier-tech/{tech_id} 遮蔽 → 404。
app.include_router(routes_alert.router, prefix=PREFIX, tags=["scan_monitor"])
app.include_router(routes_frontier.router, prefix=PREFIX, tags=["scan_monitor"])
app.include_router(routes_new_tech.router, prefix=PREFIX, tags=["new_tech_discovery"])
app.include_router(routes_signals.router, prefix=PREFIX, tags=["new_tech_discovery"])
app.include_router(routes_topics.router, prefix=PREFIX, tags=["topic_selection"])
app.include_router(routes_feedback.router, prefix=PREFIX, tags=["topic_selection"])

# ── 设置层（router 自带 /api/v1/settings 前缀） ──
app.include_router(llm_router)
app.include_router(ds_router)
app.include_router(col_router)
app.include_router(dbc_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "metaprofile-backend"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "metaprofile-backend", "docs": "/docs", "health": "/health"}
