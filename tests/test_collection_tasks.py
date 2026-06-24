"""collection cron dispatch tests: celery task + scheduler registry wiring."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.shared.worker import collection_tasks


@asynccontextmanager
async def _fake_session_ctx(session_mock):
    yield session_mock


def _patch_session(session_mock):
    return patch.object(
        collection_tasks, "get_session",
        new=lambda: _fake_session_ctx(session_mock),
    )


def test_build_registry_has_collection():
    from metaprofile.shared.scheduler import poller
    # 重置懒构造缓存，确保新 registry 含 collection
    poller.TASK_DISPATCH = {}
    poller._ensure_registry()
    assert "collection" in poller.TASK_DISPATCH


@pytest.mark.asyncio
async def test_dispatch_collection_invokes_run_collection_delay():
    """dispatch(task_type='collection', params={source_id:X}) → run_collection.delay(X)."""
    from metaprofile.shared.scheduler import poller

    captured = {}

    def fake_delay(source_id):
        captured["source_id"] = source_id
        r = MagicMock()
        r.id = "celery-collection-id"
        return r

    poller.TASK_DISPATCH = {}  # 强制重建
    with patch.object(collection_tasks.run_collection, "delay", side_effect=fake_delay):
        poller._ensure_registry()
        task_id = await poller.dispatch(
            task_type="collection", params={"source_id": 42}
        )
    assert task_id == "celery-collection-id"
    assert captured["source_id"] == 42


@pytest.mark.asyncio
async def test_async_run_collection_success_marks_completed():
    """_async_run_collection 创建 CollectionTaskORM 行, 成功置 completed + records_imported。"""
    session = AsyncMock()
    source = MagicMock()
    source.id = 7
    source.name = "ods-market"
    source.profile_type = "tech"
    source.config_json = {"db_connection_id": 1, "mode": "structure"}

    # session.get(DataSourceConfigORM, source_id) → source
    session.get = AsyncMock(return_value=source)
    # flush 后 task.id 赋值
    task_id_holder = {"id": 100}

    class FakeTask:
        def __init__(self):
            self.id = None
            self.source_id = 7
            self.source_name = "ods-market"
            self.profile_type = "tech"
            self.status = "running"
            self.records_imported = 0
            self.error_msg = None

    fake_task = FakeTask()

    def collection_task_ctor(*args, **kwargs):
        return fake_task

    with _patch_session(session), \
         patch.object(collection_tasks, "CollectionTaskORM", side_effect=collection_task_ctor), \
         patch.object(collection_tasks, "run_sql_warehouse_collection",
                      AsyncMock(return_value=128)):
        # 模拟 flush 把 id 落上
        async def _flush():
            fake_task.id = task_id_holder["id"]
        session.flush = AsyncMock(side_effect=_flush)
        result = await collection_tasks._async_run_collection(source_id=7)

    assert result["status"] == "completed"
    assert result["imported"] == 128
    assert result["task_id"] == 100
    assert fake_task.status == "completed"
    assert fake_task.records_imported == 128
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_async_run_collection_missing_source_returns_error():
    """source_id 不存在(404) → 返回 error dict, 不跑采集。"""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    with _patch_session(session), \
         patch.object(collection_tasks, "run_sql_warehouse_collection",
                      AsyncMock()) as coll:
        result = await collection_tasks._async_run_collection(source_id=999)
    assert result["status"] == "error"
    assert "999" in result["error"]
    coll.assert_not_called()


@pytest.mark.asyncio
async def test_async_run_collection_failure_marks_failed():
    """采集抛异常 → task.status=failed + error_msg + commit, 不向上抛。"""
    session = AsyncMock()
    source = MagicMock()
    source.id = 7; source.name = "ods"; source.profile_type = "tech"
    source.config_json = {}
    session.get = AsyncMock(return_value=source)

    class FakeTask:
        def __init__(self):
            self.id = None; self.status = "running"
            self.records_imported = 0; self.error_msg = None

    fake_task = FakeTask()

    with _patch_session(session), \
         patch.object(collection_tasks, "CollectionTaskORM", return_value=fake_task), \
         patch.object(collection_tasks, "run_sql_warehouse_collection",
                      AsyncMock(side_effect=Exception("db down"))):
        async def _flush():
            fake_task.id = 5
        session.flush = AsyncMock(side_effect=_flush)
        result = await collection_tasks._async_run_collection(source_id=7)

    assert result["status"] == "failed"
    assert fake_task.status == "failed"
    assert "db down" in (fake_task.error_msg or "")
    session.commit.assert_awaited()


def test_run_collection_celery_task_registered():
    """celery task 已注册到 metaprofile.collection.run。"""
    assert collection_tasks.run_collection.name == "metaprofile.collection.run"


def test_run_collection_celery_task_uses_run_async():
    """celery task 入口委托 run_async(<coroutine>)。"""
    fake_result = {"status": "completed", "imported": 5, "task_id": 1}

    async def fake_async(_source_id):
        return fake_result

    captured: list = []
    orig_run_async = collection_tasks.run_async

    def fake_run_async(coro):
        captured.append(coro)
        # 触发消费协程避免未 await 警告,然后返 fake_result
        loop_result = orig_run_async(coro)
        return fake_result

    with patch.object(collection_tasks, "_async_run_collection", fake_async), \
         patch.object(collection_tasks, "run_async", side_effect=fake_run_async):
        out = collection_tasks.run_collection(source_id=7)
    assert len(captured) == 1
    assert out == fake_result
