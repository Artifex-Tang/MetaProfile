from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from metaprofile.shared.config.logging_config import configure_logging
from metaprofile.settings_api.api.routes_llm import router as llm_router
from metaprofile.settings_api.api.routes_datasource import router as ds_router
from metaprofile.settings_api.api.routes_collection import router as col_router

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "settings_api"}
