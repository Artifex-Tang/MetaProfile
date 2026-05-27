"""LLM 评审员：对候选选题进行 4 维度评分（新颖性/重要性/可行性/表达）。"""
from __future__ import annotations

from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import ProfileBase

import structlog

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """你是技术情报研究选题评审专家。对给定选题从四个维度评分（0-1）：
- 新颖性：是否提供新视角或新技术方向
- 重要性：对行业/国家战略的潜在影响
- 可行性：调研路径是否清晰可执行
- 表达：标题和摘要是否准确、简明
请调用 review_topic 函数返回评分结果。"""


class TopicReviewScore(ProfileBase):
    novelty: float = Field(..., ge=0.0, le=1.0, description="新颖性")
    importance: float = Field(..., ge=0.0, le=1.0, description="重要性")
    feasibility: float = Field(..., ge=0.0, le=1.0, description="可行性")
    expression: float = Field(..., ge=0.0, le=1.0, description="表达")
    evidence: str = Field(..., description="评审证据要点")


class LLMReviewer:
    """LLM 4 维度评审器。"""

    caller_name = "topic_selection.llm_reviewer"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def review(self, *, title: str, summary: str) -> TopicReviewScore:
        user_prompt = f"""选题标题：{title}

选题摘要：{summary}

请对该选题进行 4 维度评分，调用 review_topic 函数返回结果。"""
        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.agent_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            function_name="review_topic",
            function_description="对选题进行新颖性/重要性/可行性/表达 4 维度评分",
            output_schema=TopicReviewScore,
            caller=self.caller_name,
        )
        return result
