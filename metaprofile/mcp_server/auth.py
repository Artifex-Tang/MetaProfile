"""MCP 端点的 Bearer token 鉴权（ASGI 中间件）。

只包在 MCP 子应用外层，不影响 REST 接口与前端静态资源。
token 未配置时直接放行（部署脚本会生成一个并写进 .env）。
"""
from __future__ import annotations

import hmac
import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_UNAUTHORIZED_BODY = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": -32001, "message": "Unauthorized: missing or invalid bearer token"},
    }
).encode()


class BearerAuthMiddleware:
    """校验 Authorization: Bearer <token>；token 为空则不校验。"""

    def __init__(self, app: Any, token: str | None) -> None:
        self._app = app
        self._token = token or None

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if self._token is None or scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        if self._is_authorized(scope):
            await self._app(scope, receive, send)
            return

        logger.warning("mcp_unauthorized", path=scope.get("path"))
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b'Bearer realm="mcp"'),
                    (b"content-length", str(len(_UNAUTHORIZED_BODY)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _UNAUTHORIZED_BODY})

    def _is_authorized(self, scope: Any) -> bool:
        for name, value in scope.get("headers", []):
            if name.lower() != b"authorization":
                continue
            raw = value.decode("latin-1").strip()
            scheme, _, presented = raw.partition(" ")
            if scheme.lower() != "bearer":
                return False
            # 定长比较，避免按字符提前返回泄漏 token 前缀
            return hmac.compare_digest(presented.strip(), self._token or "")
        return False
