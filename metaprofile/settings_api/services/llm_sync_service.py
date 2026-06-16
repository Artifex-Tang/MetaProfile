"""同步 LLM 配置到 LiteLLM Proxy。"""
from __future__ import annotations

import structlog
import httpx

from metaprofile.shared.config.settings import settings
from metaprofile.settings_api.domain.orm_models import LLMProviderConfigORM

logger = structlog.get_logger(__name__)

_LITELLM_BASE = "http://litellm:4000"


async def sync_to_litellm(cfg: LLMProviderConfigORM) -> bool:
    """向 LiteLLM 注册或更新模型，失败时静默返回 False。"""
    master_key = getattr(settings, 'llm', None)
    api_key = getattr(master_key, 'proxy_api_key', None) if master_key else None
    if not api_key:
        api_key = "sk-dev-master-key"

    payload = {
        "model_name": cfg.model_name,
        "litellm_params": {
            "model": f"openai/{cfg.model_name}",
            "api_key": cfg.api_key or "none",
            "api_base": cfg.api_base or _default_base(cfg.provider),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{_LITELLM_BASE}/model/new",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            logger.info("litellm_sync_ok", model=cfg.model_name)
            return True
    except Exception as exc:
        logger.warning("litellm_sync_failed", model=cfg.model_name, error=str(exc))
        return False


async def test_llm_connection(cfg: LLMProviderConfigORM) -> tuple[bool, str, int | None]:
    """测试 LLM 连接，返回 (success, message, latency_ms)。"""
    import time

    api_base = cfg.api_base or _default_base(cfg.provider)
    if not api_base:
        return False, "未配置 API Base URL", None

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # 兼容用户填了完整地址（含 /chat/completions）或仅 base 的情况
            base = api_base.rstrip("/")
            url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
            # 发一个最小的 chat completion 请求
            resp = await client.post(
                url,
                json={
                    "model": cfg.model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                },
                headers={
                    "Authorization": f"Bearer {cfg.api_key or ''}",
                    "Content-Type": "application/json",
                },
            )
            latency = int((time.monotonic() - t0) * 1000)
            if resp.status_code in (200, 201):
                return True, "连接成功", latency
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}", latency
    except httpx.TimeoutException:
        return False, "连接超时（15s）", None
    except Exception as exc:
        return False, str(exc)[:200], None


def _default_base(provider: str) -> str:
    defaults = {
        "openai": "https://api.openai.com/v1",
        "azure": "",
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
    return defaults.get(provider, "")
