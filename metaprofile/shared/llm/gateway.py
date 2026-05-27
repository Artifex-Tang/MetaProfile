"""
统一 LLM 调用入口。所有 LLM 请求必须通过 LLMGateway，禁止直连模型 API。

职责：
1. 路由到对应模型（extraction / relation / judge / agent / generation）
2. Token 计量与日志
3. 重试与降级
4. Function Calling 封装（见 function_calling.py）
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class LLMResponse:
    content: str
    function_call: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: int
    request_id: str


class LLMGatewayError(Exception):
    """所有 LLM 调用相关异常的基类。"""


class LLMGateway:
    """LiteLLM Proxy 客户端封装。"""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=settings.llm.proxy_base_url,
            headers={"Authorization": f"Bearer {settings.llm.proxy_api_key}"},
            timeout=settings.llm.timeout_seconds,
        )

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        functions: list[dict[str, Any]] | None = None,
        function_call: str | dict[str, str] | None = None,
        request_id: str | None = None,
        caller: str = "unknown",
    ) -> LLMResponse:
        """
        通用 chat completion 调用。

        Args:
            model: 模型名称（来自 settings.llm.*_model）
            messages: OpenAI 风格 messages
            functions: Function Calling 函数定义列表
            function_call: "auto" / "none" / {"name": "..."}
            caller: 调用方标识，用于 token_meter 日志（如 "tech_extractor"）
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if functions:
            payload["functions"] = functions
        if function_call:
            payload["function_call"] = function_call

        started = time.monotonic()
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.llm.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(
                (httpx.HTTPError, httpx.TimeoutException)
            ),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.post("/v1/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()

        latency_ms = int((time.monotonic() - started) * 1000)
        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})

        result = LLMResponse(
            content=choice.get("content", "") or "",
            function_call=choice.get("function_call"),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=model,
            latency_ms=latency_ms,
            request_id=data.get("id", "") or request_id or "",
        )

        # 异步落库 token_meter（不阻塞主流程，由 token_meter 内部处理）
        from metaprofile.shared.llm.token_meter import record_call_async

        await record_call_async(caller=caller, response=result)
        return result

    async def aclose(self) -> None:
        await self._client.aclose()


_default_gateway: LLMGateway | None = None


def get_default_gateway() -> LLMGateway:
    """获取默认 LLM 网关实例（单例）。生产环境通过 DI 注入。"""
    global _default_gateway
    if _default_gateway is None:
        _default_gateway = LLMGateway()
    return _default_gateway
