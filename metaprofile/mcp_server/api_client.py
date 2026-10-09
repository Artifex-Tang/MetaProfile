"""MCP 工具访问后端 REST 的薄客户端。

刻意走 HTTP 而不是直接 import service 层：
- 复用 readonly_guard 熔断与 pydantic 响应校验，不重复一套逻辑；
- MCP 与 backend 同容器同进程，回环 HTTP 开销可忽略。
"""
from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0


class BackendError(RuntimeError):
    """后端调用失败。status_code=0 表示根本没连上。"""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendClient:
    """按 path 调用后端 /api/v1 接口并返回解析后的 JSON。"""

    def __init__(
        self,
        base_url: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT_SECONDS
        )

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=_drop_none(params))

    async def post(self, path: str, json_body: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", path, json=json_body)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as e:
            logger.warning("mcp_backend_unreachable", url=url, error=str(e))
            raise BackendError(0, f"后端不可达 {method} {path}: {e}") from e

        if response.status_code >= 400:
            raise BackendError(
                response.status_code,
                f"后端返回 {response.status_code} ({method} {path}): "
                f"{_extract_detail(response)}",
            )

        try:
            return response.json()
        except ValueError as e:
            raise BackendError(
                response.status_code,
                f"后端未返回 JSON（{method} {path}），可能打到了 SPA fallback："
                f"{response.text[:200]}",
            ) from e


def _drop_none(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """剔除 None：httpx 会把 None 编码成空串，后端 date/float 解析会 422。"""
    if params is None:
        return None
    return {k: v for k, v in params.items() if v is not None}


def _extract_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return str(body)[:200]
