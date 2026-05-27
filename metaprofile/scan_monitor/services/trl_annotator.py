"""RAG-LLM TRL（技术成熟度）标注服务。

从 profile_tech 画像层获取技术详情，
调用 LLM 基于技术概要、当前状态、实验记录推断 TRL 等级（1-9）。
"""
from __future__ import annotations

from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import ProfileBase

import structlog

logger = structlog.get_logger(__name__)


class TRLAnnotation(ProfileBase):
    trl_level: int = Field(..., ge=1, le=9, description="技术成熟度等级 1-9")
    rationale: str = Field(..., description="判定理由")
    confidence: float = Field(..., ge=0.0, le=1.0)


SYSTEM_PROMPT = """你是技术成熟度（TRL）评估专家。
TRL 定义：
1=基础原理已证实, 2=概念已形成, 3=实验室验证, 4=实验室环境验证,
5=相关环境验证, 6=系统原型验证, 7=系统原型演示, 8=系统完成且合格,
9=实际系统已通过任务验证。
基于给定技术画像，判断当前 TRL 等级。"""


class TRLAnnotator:
    """TRL 标注器（调用 LLM 推断 TRL 等级）。"""

    caller_name = "scan_monitor.trl_annotator"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def annotate(self, *, tech_name: str, tech_summary: str, current_status: str) -> TRLAnnotation:
        user_prompt = f"""技术名称：{tech_name}

技术概述：{tech_summary}

当前状态：{current_status}

请调用 annotate_trl 函数返回 TRL 等级判定结论。"""
        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.agent_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            function_name="annotate_trl",
            function_description="判定技术成熟度 TRL 等级（1-9）",
            output_schema=TRLAnnotation,
            caller=self.caller_name,
        )
        return result
