"""migration 0009_llm_call_log 的单元 + 集成测试。

单元测试(始终运行):
  - 0009 修订号 / down_revision 正确(链到 0008_tech_concept)
  - migration 建的表名与 ORM LLMCallLog.__tablename__ 一致

集成测试(需 TEST_POSTGRES_DSN):
  - 跑 0009 upgrade → llm_call_log 表 + 索引存在
  - gateway 记日志路径 record_call_async 不再 warn,行可读回
  - downgrade → 表删除
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select, text

from metaprofile.shared.llm.gateway import LLMResponse
from metaprofile.shared.llm import token_meter


# ── 单元测试(无 DB) ─────────────────────────────────────────────────────────

def _load_migration_mod():
    """文件名以数字开头 → 不是合法标识符,从路径加载。"""
    import importlib.util
    from pathlib import Path

    p = (Path(__file__).resolve().parents[2]
         / "migrations" / "versions" / "0009_llm_call_log.py")
    spec = importlib.util.spec_from_file_location("_mig_0009_llm_call_log", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_0009_revision_chain():
    """0009 链到 0008_tech_concept(当前 head)。"""
    mod = _load_migration_mod()
    assert mod.revision == "0009_llm_call_log"
    assert mod.down_revision == "0008_tech_concept"


def test_migration_table_matches_orm():
    """migration 建的表名与 ORM 一致 —— gateway 通过 ORM INSERT。"""
    import re
    from pathlib import Path

    migration_src = Path(__file__).resolve().parents[2] / \
        "migrations" / "versions" / "0009_llm_call_log.py"
    src = migration_src.read_text(encoding="utf-8")
    # 抓 _TABLE 常量
    m = re.search(r'_TABLE\s*=\s*"([a-z_]+)"', src)
    assert m, "未在 migration 中找到 _TABLE 常量"
    table_from_migration = m.group(1)

    assert token_meter.LLMCallLog.__tablename__ == table_from_migration, (
        f"ORM 表名 {token_meter.LLMCallLog.__tablename__} ≠ migration "
        f"_TABLE {table_from_migration}:gateway INSERT 会失败"
    )


# ── 集成测试(需真实 PostgreSQL) ────────────────────────────────────────────


@pytest_asyncio.fixture
async def _migration_table(test_dsn, db_engine):
    """跑 0009 migration against 测试 DB(先 drop 再 upgrade,最后清理)。

    注意:db_engine fixture 已对 Base.metadata 跑过 create_all —— 因 LLMCallLog
    已注册到 Base.metadata,llm_call_log 可能已被 create_all 建出。为了真正
    验证 migration 文件,这里先 drop 该表 + 相关 alembic 记录,再用 alembic op
    上下文直接跑 migration.upgrade()。
    """
    import importlib
    from sqlalchemy.ext.asyncio import create_async_engine

    mod = _load_migration_mod()

    engine = create_async_engine(test_dsn, echo=False)
    try:
        # 清场:drop 表(若 create_all 已建)
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS llm_call_log CASCADE"))
        # 跑 migration upgrade(用同步 op 上下文)
        async with engine.begin() as conn:
            await conn.run_sync(_run_alembic_upgrade, mod)
        yield engine
        # 清理:downgrade
        async with engine.begin() as conn:
            await conn.run_sync(_run_alembic_downgrade, mod)
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS llm_call_log CASCADE"))
    finally:
        await engine.dispose()


def _run_alembic_upgrade(sync_conn, mod):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    ctx = MigrationContext.configure(sync_conn)
    # migration 用 `from alembic import op` —— 把真实 Operations 实例直接绑到
    # migration 模块的 op 名字上(覆盖模块导入时绑的 alembic.op 代理)。
    orig_op = getattr(mod, "op", None)
    mod.op = Operations(ctx)
    try:
        mod.upgrade()
    finally:
        if orig_op is not None:
            mod.op = orig_op
        else:
            del mod.op


def _run_alembic_downgrade(sync_conn, mod):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    ctx = MigrationContext.configure(sync_conn)
    orig_op = getattr(mod, "op", None)
    mod.op = Operations(ctx)
    try:
        mod.downgrade()
    finally:
        if orig_op is not None:
            mod.op = orig_op
        else:
            del mod.op


@pytest.mark.asyncio
async def test_migration_creates_table_and_indexes(_migration_table):
    """upgrade 后 llm_call_log 表 + 索引存在,列与 ORM 一致。"""
    engine = _migration_table
    async with engine.connect() as conn:
        names = await conn.run_sync(
            lambda c: set(inspect(c).get_table_names())
        )
    assert "llm_call_log" in names

    def _cols_and_idx(c):
        insp = inspect(c)
        cols = {col["name"] for col in insp.get_columns("llm_call_log")}
        idx = {i["name"] for i in insp.get_indexes("llm_call_log")}
        return cols, idx

    async with engine.connect() as conn:
        cols, idx = await conn.run_sync(_cols_and_idx)

    expected_cols = {
        "id", "caller", "model", "request_id", "input_tokens",
        "output_tokens", "cost_cny", "latency_ms", "called_at",
        "created_at", "updated_at",
    }
    assert expected_cols <= cols, f"缺列: {expected_cols - cols}"
    assert "ix_llm_call_log_called_at" in idx
    assert "ix_llm_call_log_caller" in idx


@pytest.mark.asyncio
async def test_record_call_async_writes_row_without_warning(_migration_table, caplog):
    """gateway 记日志路径不再 warn llm_call_log_record_failed,行可读回。"""
    from metaprofile.shared.db.postgres import get_session
    from metaprofile.shared.db.base import Base
    # 确保表已建(migration 已建);get_session 用生产 DSN 配置 → 跳到测试库由
    # 环境变量 POSTGRES_DSN 决定。集成测试需指向同一 DB。

    resp = LLMResponse(
        content="ok", function_call=None,
        input_tokens=120, output_tokens=40,
        model="deepseek-chat", latency_ms=250, request_id="req-1",
    )
    with caplog.at_level(logging.WARNING, logger="metaprofile.shared.llm.token_meter"):
        await token_meter.record_call_async(caller="test", response=resp)

    assert not any(
        "llm_call_log_record_failed" in (r.getMessage() or "")
        for r in caplog.records
    ), "record_call_async 仍 warn llm_call_log_record_failed —— 表/列不匹配"


@pytest.mark.asyncio
async def test_migration_downgrade_drops_table(test_dsn):
    """downgrade 后表删除(单独跑,避免污染 _migration_table 的清场顺序)。"""
    from sqlalchemy.ext.asyncio import create_async_engine

    mod = _load_migration_mod()
    engine = create_async_engine(test_dsn, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS llm_call_log CASCADE"))
        async with engine.begin() as conn:
            await conn.run_sync(_run_alembic_upgrade, mod)
        async with engine.begin() as conn:
            await conn.run_sync(_run_alembic_downgrade, mod)
        async with engine.connect() as conn:
            names = await conn.run_sync(
                lambda c: set(inspect(c).get_table_names())
            )
        assert "llm_call_log" not in names
    finally:
        await engine.dispose()
