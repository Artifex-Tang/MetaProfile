"""集成测试 fixtures：真实 PostgreSQL 数据库。

用法：
    TEST_POSTGRES_DSN=postgresql+asyncpg://user:pass@localhost/test_metaprofile \
    py -3.12 -m pytest tests/integration/ -v

无 TEST_POSTGRES_DSN 时，全部集成测试自动 skip。
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 导入所有 ORM 让 metadata 完整
import metaprofile.foundation.storage.orm_models  # noqa: F401
import metaprofile.new_tech_discovery.domain.orm_models  # noqa: F401
import metaprofile.profile_org.domain.orm_models  # noqa: F401
import metaprofile.profile_person.domain.orm_models  # noqa: F401
import metaprofile.profile_project.domain.orm_models  # noqa: F401
import metaprofile.profile_tech.domain.orm_models  # noqa: F401
import metaprofile.scan_monitor.domain.orm_models  # noqa: F401
import metaprofile.shared.db.orm_models  # noqa: F401
import metaprofile.topic_selection.domain.orm_models  # noqa: F401
from metaprofile.shared.db.base import Base

_DSN_ENV = "TEST_POSTGRES_DSN"
_DEFAULT_DSN = "postgresql+asyncpg://metaprofile:metaprofile@localhost:5432/test_metaprofile"


def _get_test_dsn() -> str | None:
    return os.getenv(_DSN_ENV) or (
        _DEFAULT_DSN if os.getenv("CI") else None
    )


@pytest.fixture(scope="session")
def test_dsn() -> str:
    dsn = _get_test_dsn()
    if dsn is None:
        pytest.skip(
            f"集成测试需要真实 PostgreSQL。设置 {_DSN_ENV} 环境变量后重试。"
        )
    return dsn


@pytest_asyncio.fixture(scope="session")
async def db_engine(test_dsn: str):
    """Session-scoped engine：只建/删一次表。"""
    engine = create_async_engine(test_dsn, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    """Function-scoped：每个测试用独立连接 + 事务，测试后回滚（数据不持久化）。"""
    async with db_engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(bind=conn, expire_on_commit=False, autoflush=False) as session:
            yield session
        await conn.rollback()
