"""
扫描监测核心服务：五维信号采集 + 融合评分 + LLM Agent 验证 + RAG TRL 标注。

详细方案见 0416-v2.docx 第 X 章"产业前沿技术扫描监测"。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class FrontierTechCandidate:
    """前沿技术候选。"""

    tech_id: str | None  # 关联到 profile_tech 的画像 ID（若已有画像）
    tech_name: str
    tech_domain: list[str]
    burst_score: float          # 信号A：关键词突现
    patent_score: float         # 信号B：专利异动
    citation_score: float       # 信号C：引用聚类
    invest_score: float         # 信号D：投融资热度
    policy_score: float         # 信号E：政策导向
    fusion_score: float         # 五维融合
    llm_validated: bool         # LLM Agent 4 步验证是否通过
    trl_level: int | None       # 1~9 级技术成熟度
    period_from: date
    period_to: date


class FrontierTechFusionScorer:
    """五维信号融合评分器。"""

    DEFAULT_WEIGHTS = {
        "burst": 0.20,
        "patent": 0.25,
        "citation": 0.20,
        "invest": 0.20,
        "policy": 0.15,
    }

    def fuse(
        self,
        *,
        burst: float,
        patent: float,
        citation: float,
        invest: float,
        policy: float,
        weights: dict[str, float] | None = None,
    ) -> float:
        """加权融合。各信号已归一化到 [0, 1]。"""
        w = weights or self.DEFAULT_WEIGHTS
        return (
            w["burst"] * burst
            + w["patent"] * patent
            + w["citation"] * citation
            + w["invest"] * invest
            + w["policy"] * policy
        )
