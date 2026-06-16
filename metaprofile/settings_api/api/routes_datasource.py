from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.shared.db.session import get_db
from metaprofile.settings_api.domain.orm_models import DataSourceConfigORM
from metaprofile.settings_api.schemas.models import (
    DataSourceConfigCreate,
    DataSourceConfigOut,
    DataSourceConfigUpdate,
)

router = APIRouter(prefix="/api/v1/settings/datasources", tags=["数据源配置"])


@router.get("", response_model=list[DataSourceConfigOut])
async def list_datasources(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(DataSourceConfigORM).order_by(DataSourceConfigORM.id)
    )).scalars().all()
    return rows


@router.post("", response_model=DataSourceConfigOut, status_code=201)
async def create_datasource(body: DataSourceConfigCreate, db: AsyncSession = Depends(get_db)):
    ds = DataSourceConfigORM(**body.model_dump())
    db.add(ds)
    await db.flush()
    await db.refresh(ds)
    return ds


@router.get("/{ds_id}", response_model=DataSourceConfigOut)
async def get_datasource(ds_id: int, db: AsyncSession = Depends(get_db)):
    ds = await db.get(DataSourceConfigORM, ds_id)
    if not ds:
        raise HTTPException(404, "数据源不存在")
    return ds


@router.put("/{ds_id}", response_model=DataSourceConfigOut)
async def update_datasource(ds_id: int, body: DataSourceConfigUpdate, db: AsyncSession = Depends(get_db)):
    ds = await db.get(DataSourceConfigORM, ds_id)
    if not ds:
        raise HTTPException(404, "数据源不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ds, k, v)
    await db.flush()
    await db.refresh(ds)  # 刷新服务端默认列(updated_at)，避免 response 序列化时 MissingGreenlet
    return ds


@router.delete("/{ds_id}", status_code=204)
async def delete_datasource(ds_id: int, db: AsyncSession = Depends(get_db)):
    ds = await db.get(DataSourceConfigORM, ds_id)
    if not ds:
        raise HTTPException(404, "数据源不存在")
    await db.delete(ds)


@router.get("/templates/list")
async def list_templates():
    """返回各数据源类型的配置模板。"""
    return {
        "rest_api": {
            "url": "https://api.example.com/data",
            "method": "GET",
            "auth_type": "bearer",
            "auth_token": "your-token",
            "headers": {},
            "query_params": {"format": "json"},
            "response_items_path": "data.items",
            "field_mapping": {
                "tech_name_cn": "name",
                "tech_name_en": "nameEn",
                "tech_summary": "description",
                "tech_domain": "domains",
                "current_status": "status",
                "trend": "trend",
            },
            "pagination_enabled": True,
            "page_param": "page",
            "size_param": "page_size",
            "page_size": 50,
            "max_pages": 10,
        },
        "rss": {
            "feed_url": "https://arxiv.org/rss/cs.AI",
            "field_mapping": {
                "tech_name_cn": "title",
                "tech_summary": "summary",
            },
            "keyword_filter": ["quantum", "neural"],
            "max_items": 100,
        },
        "nsfc": {
            "keywords": "量子计算",
            "max_pages": 5,
            "field_mapping": {
                "name_cn": ["projectName"],
                "tech_domain": ["subject"],
                "start_date": "approvalYear",
                "main_orgs": ["hostUnit"],
                "research_content": ["objective"],
                "progress": ["results"],
            },
        },
        "patent_cnipa": {
            "keywords": "量子纠错",
            "api_key": "your-cnipa-api-key",
            "max_pages": 5,
        },
    }
