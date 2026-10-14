"""LLM Rotolo 五属性 rubric 评分器(Phase C3,漏斗末端才调用)。

Rotolo/Hicks/Martin 2015《What is an emerging technology?》五属性:
radical novelty / fast growth / prominent impact / coherence / ambiguity。
每属性 1-5 分;×N 次取中位(temperature 不可控则以中位抗抖动)。
"""
from __future__ import annotations

import statistics

from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import ProfileBase


class RotoloScores(ProfileBase):
    novelty: int = Field(..., ge=1, le=5, description="激进新颖性")
    growth: int = Field(..., ge=1, le=5, description="相对快速增长")
    impact: int = Field(..., ge=1, le=5, description="显著影响潜力")
    coherence: int = Field(..., ge=1, le=5, description="概念内部一致性")
    ambiguity: int = Field(..., ge=1, le=5, description="应用场景仍含糊(高=早期)")
    rationale: str = Field(..., description="评分依据要点")
    confidence: float = Field(..., ge=0.0, le=1.0)


SYSTEM_PROMPT = """你是技术情报评估专家,按 Rotolo(2015)五属性给候选颠覆性技术打 rubric 分。
判定基准(每属性 1-5 整数):
- novelty 激进新颖: 1=既有技术组合微调; 5=全新科学原理/全新技术范式
- growth 增长: 1=停滞; 5=爆发式增长(近窗倍增)
- impact 影响: 1=利基改善; 5=可重塑产业格局/跨域影响
- coherence 一致性: 1=社区定义严重分裂; 5=术语/范式高度收敛
- ambiguity 含糊性: 1=应用已定型; 5=应用场景高度未定(早期颠覆特征)
只依据证据材料,材料不足的属性打 3 分并在 rationale 说明。"""


class RotoloRubricValidator:
    caller_name = "new_tech.rotolo_rubric"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def validate(self, *, name: str, evidence_pack: str) -> RotoloScores:
        user_prompt = f"""候选技术域:{name}

证据材料(统计指标+代表专利标题+新兴跨域对):
{evidence_pack}

请调用 rate_rotolo 函数按五属性打分。"""
        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.agent_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            function_name="rate_rotolo",
            function_description="按 Rotolo 五属性对候选颠覆性技术 rubric 打分",
            output_schema=RotoloScores,
            caller=self.caller_name,
        )
        return result


_DIMS = ("novelty", "growth", "impact", "coherence", "ambiguity")


def median_verdict(runs: list[RotoloScores]) -> tuple[dict, float, str, str]:
    """多次评分 → 各维中位 + 综合分 + 判定 + 依据。

    判定:综合中位 ≥4.0 → 是; ≤2.5 → 否; 其间 → 待定。
    返回 (scores_dict, composite, verdict, rationale)。
    """
    if not runs:
        return {}, 0.0, "pending"
    scores = {d: statistics.median([getattr(r, d) for r in runs]) for d in _DIMS}
    composite = statistics.mean(scores.values())
    verdict = "是" if composite >= 4.0 else ("否" if composite <= 2.5 else "待定")
    rationale = runs[0].rationale if len(runs) == 1 else " / ".join(
        {r.rationale[:120] for r in runs},
    )
    return scores, round(composite, 3), verdict, rationale  # type: ignore[return-value]
