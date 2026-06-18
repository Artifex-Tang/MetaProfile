"""db_connections CRUD 服务。密码加密存 password_enc，输出脱敏（见 DbConnectionOut）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.security import encrypt_pw
from metaprofile.settings_api.schemas.models import (
    DbConnectionCreate,
    DbConnectionUpdate,
)


class DbConnectionService:
    async def list(self, db: AsyncSession) -> list[DBConnectionORM]:
        rows = (
            await db.execute(
                select(DBConnectionORM).order_by(DBConnectionORM.id)
            )
        ).scalars().all()
        return list(rows)

    async def get(self, db: AsyncSession, conn_id: int) -> DBConnectionORM | None:
        return await db.get(DBConnectionORM, conn_id)

    async def create(self, db: AsyncSession, body: DbConnectionCreate) -> DBConnectionORM:
        orm = DBConnectionORM(
            name=body.name,
            dialect=body.dialect,
            host=body.host,
            port=body.port,
            database=body.database,
            username=body.username,
            password_enc=encrypt_pw(body.password),
            charset=body.charset,
            pool_size=body.pool_size,
            read_only=body.read_only,
            is_enabled=body.is_enabled,
        )
        db.add(orm)
        await db.flush()
        await db.refresh(orm)
        return orm

    async def update(
        self, db: AsyncSession, conn_id: int, body: DbConnectionUpdate
    ) -> DBConnectionORM | None:
        orm = await db.get(DBConnectionORM, conn_id)
        if orm is None:
            return None
        data = body.model_dump(exclude_none=True)
        if "password" in data:
            orm.password_enc = encrypt_pw(data.pop("password"))
        for k, v in data.items():
            setattr(orm, k, v)
        await db.flush()
        await db.refresh(orm)
        return orm

    async def delete(self, db: AsyncSession, conn_id: int) -> bool:
        orm = await db.get(DBConnectionORM, conn_id)
        if orm is None:
            return False
        await db.delete(orm)
        await db.flush()
        return True
