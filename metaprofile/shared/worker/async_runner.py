"""celery worker 内跑 async 协程的统一入口:复用 per-worker 持久 event loop。

问题:celery 任务体里直接 `asyncio.run(coro)` 每次建+关一个 loop。而
`shared.db.postgres._engine` 是模块级单例,asyncpg 连接池一旦在某 loop 上
checkout 连接,连接就绑定该 loop。第一个任务 `asyncio.run` 关闭 loop1 后,
第二个任务 `asyncio.run` 建 loop2,但引擎连接仍绑在已关的 loop1 →
`RuntimeError: Event loop is closed` / "attached to a different loop"。

修:worker 进程内持有一个不关闭的 loop,所有任务复用之。engine 连接 / httpx
全部绑同一 loop,跨任务安全。celery prefork 在 import 后 fork,engine 懒构造,
每个 fork worker 各自的持久 loop 上建引擎,无跨 fork 共享。
"""
from __future__ import annotations

import asyncio
import threading
from typing import Awaitable, TypeVar

_T = TypeVar("_T")

_loop: asyncio.AbstractEventLoop | None = None
_lock = threading.Lock()


def run_async(coro: Awaitable[_T]) -> _T:
    """在 worker 持久 loop 上跑协程,返回结果。线程安全(loop 单例建一次)。"""
    global _loop
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
        loop = _loop
    return loop.run_until_complete(coro)
