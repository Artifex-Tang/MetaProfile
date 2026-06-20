from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from metaprofile.shared.config.logging_config import configure_logging
from metaprofile.settings_api.api.routes_llm import router as llm_router
from metaprofile.settings_api.api.routes_datasource import router as ds_router
from metaprofile.settings_api.api.routes_collection import router as col_router
from metaprofile.settings_api.api.routes_enrichment_tasks import router as enrich_tasks_router
from metaprofile.settings_api.api.routes_scheduler import router as scheduler_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时配置日志（非 import 时，避免测试导入 main 触发全局 structlog 污染）
    configure_logging()
    logger.info("settings_api_startup")
    yield
    logger.info("settings_api_shutdown")


app = FastAPI(
    title="MetaProfile Settings API",
    description="LLM 配置 / 数据源配置 / 采集任务管理",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(llm_router)
app.include_router(ds_router)
app.include_router(col_router)
app.include_router(enrich_tasks_router)
app.include_router(scheduler_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "settings_api"}
