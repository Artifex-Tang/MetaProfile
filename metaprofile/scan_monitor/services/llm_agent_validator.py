"""
LLM Agent 前沿性 4 步验证。

输入：候选前沿技术（含五维分项得分）
4 步：
  Step 1 - 真实性核验：LLM 检索画像层确认技术真实存在
  Step 2 - 时效性核验：LLM 判断技术是否在监测窗口内活跃
  Step 3 - 突破性判定：LLM 评估技术相对现有技术体系的突破性
  Step 4 - 自洽性核验：LLM 综合上述结论，输出"是 / 否 / 待定"+依据
"""
from __future__ import annotations

from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import ProfileBase


class FrontierAgentVerdict(ProfileBase):
    realness: bool = Field(..., description="技术真实存在")
    timeliness: bool = Field(..., description="监测窗口内活跃")
    breakthrough: bool = Field(..., description="相对现有技术有突破性")
    final_decision: str = Field(..., description="是 / 否 / 待定")
    evidence: str = Field(..., description="证据要点")
    confidence: float = Field(..., ge=0.0, le=1.0)


SYSTEM_PROMPT = """你是产业技术情报评估专家，按 4 步流程验证一项候选前沿技术。
判定标准：
- 真实性：能找到至少 3 个独立可信来源（论文/专利/政府报告/权威媒体）
- 时效性：监测窗口内有实质性进展（≥3 件相关专利或≥2 篇核心论文）
- 突破性：相对现有主流方案有 ≥1 项指标的显著改善
- 最终结论：三项均为真 → 是；任一为假且无歧义 → 否；存在歧义 → 待定
"""


class FrontierAgentValidator:
    caller_name = "scan_monitor.frontier_agent"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def validate(
        self, *, tech_name: str, evidence_pack: str
    ) -> FrontierAgentVerdict:
        user_prompt = f"""候选前沿技术：{tech_name}

证据材料（论文 / 专利 / 投融资 / 政策摘要）：
{evidence_pack}

请按 4 步验证，调用 verify_frontier_tech 函数返回结论。
"""
        result, _ = await call_with_schema(
            gateway=self._gateway,
            model=settings.llm.agent_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            function_name="verify_frontier_tech",
            function_description="对候选前沿技术进行真实性/时效性/突破性 4 步验证",
            output_schema=FrontierAgentVerdict,
            caller=self.caller_name,
        )
        return result
