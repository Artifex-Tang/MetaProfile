"""通用异步重试装饰器（基于 tenacity）。"""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

import structlog
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def async_retry(
    *,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """装饰器：为异步函数添加指数退避重试。

    用法：
        @async_retry(max_attempts=3, exceptions=(httpx.HTTPError,))
        async def call_external(): ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(exceptions),
                before_sleep=before_sleep_log(logger, log_level="warning"),
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
