"""run_async: celery worker 内复用 per-worker 持久 event loop。

回归测 asyncio.run 闭 loop 致 asyncpg 连接绑死已关 loop 的 bug。
"""
import asyncio

from metaprofile.shared.worker.async_runner import run_async


async def _add() -> int:
    return 2 + 2


async def _current_loop():
    return asyncio.get_running_loop()


def test_run_async_returns_value():
    assert run_async(_add()) == 4


def test_run_async_reuses_same_loop_across_calls():
    """关键回归:两次调用跑在同一持久 loop(非 asyncio.run 每次建+关)。"""
    loop1 = run_async(_current_loop())
    loop2 = run_async(_current_loop())
    assert loop1 is loop2  # 同一 loop 对象 → asyncpg 连接跨任务安全


def test_run_async_loop_not_closed_after_call():
    """跑完不关 loop(否则下个任务 asyncpg 连接绑死)。"""
    loop = run_async(_current_loop())
    assert loop.is_closed() is False
