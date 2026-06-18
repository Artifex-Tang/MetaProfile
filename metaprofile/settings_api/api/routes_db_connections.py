"""数据连接（ODS Doris 等外部 DB）CRUD 路由。密码加密存、脱敏读。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.settings_api.schemas.models import (
    DbConnectionCreate,
    DbConnectionOut,
    DbConnectionUpdate,
)
from metaprofile.settings_api.services.db_connection_service import DbConnectionService
from metaprofile.shared.db.session import get_db

router = APIRouter(prefix="/api/v1/settings/db-connections", tags=["数据连接配置"])

_svc = DbConnectionService()


@router.get("", response_model=list[DbConnectionOut])
async def list_db_connections(db: AsyncSession = Depends(get_db)):
    return await _svc.list(db)


@router.post("", response_model=DbConnectionOut, status_code=201)
async def create_db_connection(body: DbConnectionCreate, db: AsyncSession = Depends(get_db)):
    return await _svc.create(db, body)


@router.get("/{conn_id}", response_model=DbConnectionOut)
async def get_db_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    conn = await _svc.get(db, conn_id)
    if not conn:
        raise HTTPException(404, "数据连接不存在")
    return conn


@router.put("/{conn_id}", response_model=DbConnectionOut)
async def update_db_connection(
    conn_id: int, body: DbConnectionUpdate, db: AsyncSession = Depends(get_db)
):
    conn = await _svc.update(db, conn_id, body)
    if not conn:
        raise HTTPException(404, "数据连接不存在")
    return conn


@router.delete("/{conn_id}", status_code=204)
async def delete_db_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    ok = await _svc.delete(db, conn_id)
    if not ok:
        raise HTTPException(404, "数据连接不存在")
    return None
