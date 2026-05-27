"""
LLM 调用 Token 计量与日志。

每次调用记录入 llm_call_log 表，用于成本核算与审计追溯。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import structlog
from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from metaprofile.shared.db.base import Base, TimestampMixin
from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.llm.gateway import LLMResponse

logger = structlog.get_logger(__name__)

# 模型单价表（每千 token，单位元）。生产环境从配置加载。
MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    # model_name: (input_per_1k, output_per_1k)
    "qwen2.5-72b-instruct": (Decimal("0.02"), Decimal("0.06")),
    "deepseek-chat": (Decimal("0.001"), Decimal("0.002")),
    "bge-large-zh-v1.5": (Decimal("0.0005"), Decimal("0")),
}


class LLMCallLog(Base, TimestampMixin):
    __tablename__ = "llm_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    caller: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_cny: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


def estimate_cost_cny(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return Decimal("0")
    in_price, out_price = pricing
    return (
        Decimal(input_tokens) / Decimal(1000) * in_price
        + Decimal(output_tokens) / Decimal(1000) * out_price
    )


async def record_call_async(*, caller: str, response: LLMResponse) -> None:
    """落库一条 LLM 调用日志。失败仅日志告警，不向上抛。"""
    try:
        cost = estimate_cost_cny(
            response.model, response.input_tokens, response.output_tokens
        )
        record = LLMCallLog(
            caller=caller,
            model=response.model,
            request_id=response.request_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_cny=cost,
            latency_ms=response.latency_ms,
            called_at=datetime.utcnow(),
        )
        async with get_session() as session:
            session.add(record)
    except Exception as exc:  # 计量失败不能影响主流程
        logger.warning(
            "llm_call_log_record_failed",
            caller=caller,
            model=response.model,
            error=str(exc),
        )
