"""Alembic 迁移环境。

支持同步/异步两种运行模式：
  - online async：通过 asyncpg 连接实际 DB（run_async_migrations）
  - offline：生成纯 SQL 脚本（run_migrations_offline）
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── 导入所有 ORM 模型确保元数据完整 ──────────────────────────────────────────
# foundation
import metaprofile.foundation.storage.orm_models  # noqa: F401
# shared
import metaprofile.shared.db.orm_models  # noqa: F401
# profile 画像层
import metaprofile.profile_tech.domain.orm_models  # noqa: F401
import metaprofile.profile_org.domain.orm_models  # noqa: F401
import metaprofile.profile_project.domain.orm_models  # noqa: F401
import metaprofile.profile_person.domain.orm_models  # noqa: F401
# 分析层
import metaprofile.scan_monitor.domain.orm_models  # noqa: F401
import metaprofile.new_tech_discovery.domain.orm_models  # noqa: F401
import metaprofile.topic_selection.domain.orm_models  # noqa: F401

from metaprofile.shared.db.base import Base

config = context.config

# 读取 ini 中的 logging 配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 允许通过环境变量覆盖数据库连接
db_url = os.getenv("POSTGRES_DSN") or config.get_main_option("sqlalchemy.url")
if db_url and db_url.startswith("postgresql://"):
    # asyncpg 需要 postgresql+asyncpg 协议
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


# ── offline 模式 ──────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """生成 SQL 脚本，不需要真实 DB 连接。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── online async 模式 ─────────────────────────────────────────────────────────

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步方式连接 DB 并运行迁移。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
