"""
SQLAlchemy 2.0 异步引擎与会话工厂。

用法：
    async with get_session() as session:
        ...
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from metaprofile.shared.config.settings import settings
from metaprofile.shared.db.base import Base

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            str(settings.postgres.dsn),
            pool_size=settings.postgres.pool_size,
            max_overflow=settings.postgres.max_overflow,
            echo=settings.postgres.echo,
            pool_pre_ping=True,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """业务代码统一使用的 async session 上下文管理器。"""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def fastapi_session_dep() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖注入：from fastapi import Depends; Depends(fastapi_session_dep)"""
    async with get_session() as s:
        yield s


async def init_db() -> None:
    """初始化所有表，仅供测试与初始化脚本使用，生产用 Alembic 迁移。"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
