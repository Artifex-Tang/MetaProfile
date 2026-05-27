"""策略 E：LLM RAG 多角度选题生成。

结合前沿技术清单 + 政策关键词，调用 LLM 生成候选选题标题+摘要，
并为每条生成候选打出生成置信分。
"""
from __future__ import annotations

from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import ProfileBase
from metaprofile.topic_selection.services.input_aggregator import AggregatedInput

import structlog

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """你是产业技术情报分析专家，根据给定的前沿技术清单和政策关键词，
生成若干有研究价值的选题候选。每个选题需具备：
1. 明确的技术方向
2. 产业应用场景
3. 政策或资本背景支撑
请调用 generate_topics 函数返回候选列表。"""


class TopicSuggestion(ProfileBase):
    title: str = Field(..., description="选题标题（20-50字）")
    summary: str = Field(..., description="选题摘要（100-200字）")
    confidence: float = Field(..., ge=0.0, le=1.0, description="生成置信分")
    related_tech_names: list[str] = Field(default_factory=list)


class TopicSuggestions(ProfileBase):
    topics: list[TopicSuggestion]


class LLMRagStrategyScorer:
    """LLM RAG 生成策略。"""

    caller_name = "topic_selection.llm_rag"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def generate(
        self,
        aggregated: AggregatedInput,
        target_count: int = 10,
    ) -> list[TopicSuggestion]:
        tech_names = [ft.get("tech_name", "") for ft in aggregated.frontier_techs[:20]]
        policy_kws = aggregated.policy_keywords[:20]
        user_prompt = f"""前沿技术清单（Top 20）：
{", ".join(tech_names) or "无"}

政策关键词：
{", ".join(policy_kws) or "无"}

请生成 {target_count} 个候选选题，调用 generate_topics 函数返回结果。"""
        try:
            result, _ = await call_with_schema(
                gateway=self._gateway,
                model=settings.llm.agent_model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                function_name="generate_topics",
                function_description=f"生成 {target_count} 个候选选题",
                output_schema=TopicSuggestions,
                caller=self.caller_name,
            )
            return result.topics
        except Exception as exc:
            logger.warning("llm_rag_generate_failed", error=str(exc))
            return []

    @staticmethod
    def score_for_candidate(suggestion: TopicSuggestion) -> float:
        return suggestion.confidence
