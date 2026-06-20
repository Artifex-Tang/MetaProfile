"""
统一 LLM 调用入口。所有 LLM 请求必须通过 LLMGateway，禁止直连模型 API。

直连模式（2026-06-19）：LLMGateway 直接调用 llm_provider_configs 表中激活的
配置（is_default 优先 → 最近一条），用其 api_base + api_key + model_name 发
OpenAI 兼容 /chat/completions。不再依赖 LiteLLM Proxy（litellm 容器无 DB，
/model/new 永远 400）。原 LiteLLM 路径作 legacy 兜底（settings.llm.use_litellm=True 时）。

职责：
1. 解析激活的 LLMProviderConfig → 直连 provider
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
from sqlalchemy import text
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


# provider → 默认 OpenAI 兼容 base URL（api_base 缺省时用）
_PROVIDER_DEFAULT_BASE: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
    "baichuan": "https://api.baichuan-ai.com/v1",
    "minimax": "https://api.minimax.chat/v1",
    "yi": "https://api.lingyiwanwu.com/v1",
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "together": "https://api.together.xyz/v1",
    "mistral": "https://api.mistral.ai/v1",
    "cohere": "https://api.cohere.ai/v1",
}


async def load_active_llm_config() -> dict[str, Any] | None:
    """从 llm_provider_configs 取激活配置：is_default 优先，否则最近一条 enabled。

    raw SQL 避免 shared → settings_api ORM 的层间环。返回 dict 或 None。
    """
    from metaprofile.shared.db.postgres import get_session
    async with get_session() as s:
        row = (await s.execute(text(
            "SELECT id, provider, model_name, api_key, api_base, model_role, is_default "
            "FROM llm_provider_configs WHERE is_enabled = true "
            "ORDER BY is_default DESC, id DESC LIMIT 1"
        ))).first()
    return dict(row._mapping) if row else None


def _resolve_url(api_base: str | None, provider: str) -> str:
    base = (api_base or _PROVIDER_DEFAULT_BASE.get(provider, "")).rstrip("/")
    if not base:
        raise LLMGatewayError(f"provider={provider} 无 api_base 且无内置默认 URL，请在系统配置填写")
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


class LLMGateway:
    """直连 provider 的 LLM 网关。complete() 用激活配置的 api_base/key/model_name 直发。"""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        # legacy: 旧测试可能注入 client；直连模式忽略，按激活配置每次建 client
        self._client = client

    async def complete(
        self,
        *,
        model: str | None = None,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        functions: list[dict[str, Any]] | None = None,
        function_call: str | dict[str, str] | None = None,
        request_id: str | None = None,
        caller: str = "unknown",
    ) -> LLMResponse:
        """
        通用 chat completion 调用（OpenAI 兼容）。

        model 参数仅为调用方语义保留；实际用激活配置的 model_name（直连模式）。
        """
        cfg = await load_active_llm_config()
        if not cfg:
            raise LLMGatewayError("无可用 LLM 配置：请在系统配置添加并启用/设为默认")

        url = _resolve_url(cfg["api_base"], cfg["provider"])
        payload: dict[str, Any] = {
            "model": cfg["model_name"],
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if functions:
            # 现代 tools API（legacy functions 已废弃，glm/openai/ollama/vllm 均支持 tools）
            payload["tools"] = [{"type": "function", "function": f} for f in functions]
        if function_call:
            # legacy function_call → tool_choice。
            # 注意：zhipu(glm) 等只接受字符串形式("auto"/"none"/"required")，
            # 对象形式 {"type":"function",...} 会 400(code 1210)。单工具场景下
            # "auto" 等价强制（模型无其它工具可调），跨 provider 最兼容。
            if isinstance(function_call, dict) and function_call.get("name"):
                payload["tool_choice"] = "auto"
            else:
                payload["tool_choice"] = function_call
        headers = {
            "Authorization": f"Bearer {cfg['api_key'] or ''}",
            "Content-Type": "application/json",
        }

        started = time.monotonic()
        data: dict[str, Any] = {}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.llm.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(
                (httpx.HTTPError, httpx.TimeoutException)
            ),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=settings.llm.timeout_seconds) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()

        latency_ms = int((time.monotonic() - started) * 1000)
        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})

        # 优先 tool_calls（现代 API），回退 function_call（legacy）——兼容新旧 provider
        fn_call = None
        tool_calls = choice.get("tool_calls") or []
        if tool_calls:
            tc = tool_calls[0]
            tf = tc.get("function", {}) or {}
            fn_call = {"name": tf.get("name"), "arguments": tf.get("arguments", "")}
        elif choice.get("function_call"):
            fn_call = choice.get("function_call")

        result = LLMResponse(
            content=choice.get("content", "") or "",
            function_call=fn_call,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=cfg["model_name"],
            latency_ms=latency_ms,
            request_id=data.get("id", "") or request_id or "",
        )

        # 异步落库 token_meter（不阻塞主流程）
        from metaprofile.shared.llm.token_meter import record_call_async

        await record_call_async(caller=caller, response=result)
        return result

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()


_default_gateway: LLMGateway | None = None


def get_default_gateway() -> LLMGateway:
    """获取默认 LLM 网关实例（单例）。生产环境通过 DI 注入。"""
    global _default_gateway
    if _default_gateway is None:
        _default_gateway = LLMGateway()
    return _default_gateway
