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

import hashlib
from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import WeakSignalORM
from metaprofile.new_tech_discovery.services.adaptive_threshold import AdaptiveThreshold
from metaprofile.new_tech_discovery.services.signal_metrics import (
    build_term_stats,
    build_windows,
    burst_score,
    coherence_score,
    diversity_score,
    novelty_score,
    velocity_score,
)
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


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
    diversity: float           # 来源多样性
    velocity: float            # 增速
    period_from: date
    period_to: date
    evidence_doc_ids: list[str]


class WeakSignalExtractor:
    """从原始语料中提取候选弱信号（语料驱动，§4.11）。"""

    def __init__(
        self,
        *,
        corpus_loader=None,
        db_connection_id: int | None = None,
        quantifier: SignalStrengthQuantifier | None = None,
    ) -> None:
        self._loader = corpus_loader
        self._db_connection_id = (
            db_connection_id or settings.weak_signal.corpus_db_connection_id
        )
        self._quantifier = quantifier or SignalStrengthQuantifier()

    async def extract(
        self,
        *,
        db: AsyncSession,
        domain: str | None = None,
        period_from: date,
        period_to: date,
    ) -> list[WeakSignal]:
        """端到端提取弱信号并落库。

        步骤：
        1. 构建历史+当前窗口（lookback/window 月）
        2. 拉取 lookback_start..period_to 全期语料
        3. build_term_stats → 每候选词项的窗口/源统计
        4. 逐项算 burst/novelty/diversity/velocity/coherence → strength
        5. 自适应阈值 + burst_theta 过滤 → 弱信号
        6. 落 WeakSignalORM（signal_id 幂等）
        """
        if self._db_connection_id is None:
            logger.warning("weak_signal_no_db_connection_id")
            return []

        ws = settings.weak_signal
        windows = build_windows(
            period_from, period_to,
            lookback_months=ws.lookback_months, window_months=ws.window_months,
        )
        history_idx = [i for i, w in enumerate(windows) if w.is_history]
        current_idx = [i for i, w in enumerate(windows) if not w.is_history]
        n_history = len(history_idx)

        lookback_start = windows[0].start if windows else period_from
        docs = await self._load_corpus(lookback_start, period_to, db)

        term_stats = build_term_stats(docs, windows, min_df=2)

        candidates: list[dict] = []
        for ts in term_stats:
            df_current = (
                sum(ts.df_by_window[i] for i in current_idx) if current_idx else 0
            )
            df_history = [ts.df_by_window[i] for i in history_idx]
            burst = burst_score(df_current, df_history) if df_history else 0.0
            seen = sum(1 for i in history_idx if ts.df_by_window[i] > 0)
            novelty = novelty_score(seen, n_history)
            diversity = diversity_score(ts.df_by_source)
            recent = [
                ts.df_by_window[i]
                for i in current_idx[-ws.velocity_recent_windows:]
            ]
            velocity = velocity_score(recent, tau_threshold=ws.mk_tau_threshold)
            cur_sw = ts.df_by_source_window[current_idx[-1]] if current_idx else {}
            prev_sw = (
                ts.df_by_source_window[current_idx[-2]]
                if len(current_idx) >= 2 else {}
            )
            coherence = coherence_score(cur_sw, prev_sw)
            strength = self._quantifier.quantify(
                novelty=novelty, coherence=coherence,
                diversity=diversity, velocity=velocity,
            )
            candidates.append({
                "term": ts.term, "strength": strength, "burst": burst,
                "novelty": novelty, "diversity": diversity,
                "velocity": velocity, "coherence": coherence,
                "is_entity": ts.is_entity, "df_current": df_current,
            })

        if not candidates:
            return []

        threshold = await self._compute_threshold(db, domain)

        signals: list[WeakSignal] = []
        for c in candidates:
            if c["strength"] < threshold and c["burst"] < ws.burst_theta:
                continue
            kw = [c["term"]]
            sig_id = "WS-" + hashlib.md5("|".join(kw).encode()).hexdigest()[:16]
            sig = WeakSignal(
                signal_id=sig_id, keywords=kw,
                related_tech_ids=[], related_org_ids=[], related_person_ids=[],
                strength=round(c["strength"], 4),
                novelty=round(c["novelty"], 4),
                coherence=round(c["coherence"], 4),
                diversity=round(c["diversity"], 4),
                velocity=round(c["velocity"], 4),
                period_from=period_from, period_to=period_to,
                evidence_doc_ids=[],
            )
            orm = WeakSignalORM(
                signal_id=sig.signal_id, keywords=sig.keywords,
                related_tech_ids=[], related_org_ids=[], related_person_ids=[],
                evidence_doc_ids=[], domain=domain, status="active",
                period_from=sig.period_from, period_to=sig.period_to,
                strength=sig.strength, novelty=sig.novelty,
                coherence=sig.coherence, diversity=sig.diversity,
                velocity=sig.velocity,
            )
            db.add(orm)
            signals.append(sig)
        await db.flush()
        logger.info(
            "weak_signal_extracted", count=len(signals), threshold=threshold,
            candidates=len(candidates),
        )
        return signals

    async def _load_corpus(self, start: date, end: date, db: AsyncSession):
        if self._loader is None:
            from metaprofile.new_tech_discovery.services.corpus_loader import CorpusLoader
            self._loader = CorpusLoader()
        docs = []
        for source in ("science", "patent", "market", "attachment"):
            docs.extend(
                await self._loader.load(
                    self._db_connection_id, source, start, end, session=db,
                )
            )
        return docs

    async def _compute_threshold(self, db: AsyncSession, domain: str | None) -> float:
        return await AdaptiveThreshold(db).compute(domain=domain)


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
