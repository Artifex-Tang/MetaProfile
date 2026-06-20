"""
弱信号识别核心服务。

对应课题创新点 2：复杂异构数据驱动的弱信号识别。

四大子组件：
1. NLP 弱信号提取（关键词突现 + 主题演化 + 命名实体异常）
2. 异常检测（孤立森林 / Local Outlier Factor / Autoencoder）
3. 趋势识别（多变量时间序列分解 + Mann-Kendall 趋势检验）
4. 信号关联网络（图嵌入 + 社区发现）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class WeakSignal:
    signal_id: str
    keywords: list[str]
    related_tech_ids: list[str]
    related_org_ids: list[str]
    related_person_ids: list[str]
    strength: float            # [0, 1]
    novelty: float             # 新颖度
    coherence: float           # 内部一致性
    period_from: date
    period_to: date
    evidence_doc_ids: list[str]


class WeakSignalExtractor:
    """从原始语料中提取候选弱信号。"""

    async def extract(
        self,
        *,
        domain: str | None = None,
        period_from: date,
        period_to: date,
    ) -> list[WeakSignal]:
        """端到端提取弱信号。

        步骤：
        1. 拉取期内语料（论文/专利/会议预告/招聘启事/招标公告等）
        2. 关键词突现检测（Kleinberg 算法）+ 主题演化（LDA / BERTopic）
        3. 命名实体异常（新出现高频实体）
        4. 多模型融合，输出候选弱信号
        """
        # TODO: 实现详见 CLAUDE_CODE_PLAN 阶段 4
        return []


class SignalStrengthQuantifier:
    """弱信号强度量化器（衡量"虽弱但值得关注"程度）。"""

    def __init__(self, weights: tuple[float, float, float, float] | None = None) -> None:
        from metaprofile.shared.config.settings import settings
        ws = settings.weak_signal
        self._w = weights if weights is not None else (
            ws.w_novelty, ws.w_coherence, ws.w_diversity, ws.w_velocity,
        )

    def quantify(
        self,
        *,
        novelty: float,
        coherence: float,
        diversity: float,   # 来源多样性
        velocity: float,    # 增速
    ) -> float:
        """加权融合 4 个维度，输出 [0, 1] 强度分。"""
        wn, wc, wd, wv = self._w
        return wn * novelty + wc * coherence + wd * diversity + wv * velocity
