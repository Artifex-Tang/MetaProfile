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
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import (
    SignalNetworkEdgeORM,
    WeakSignalORM,
)
from metaprofile.new_tech_discovery.services.adaptive_threshold import AdaptiveThreshold
from metaprofile.new_tech_discovery.services.entity_linker import EntityLinker
from metaprofile.new_tech_discovery.services.evidence_builder import (
    build_term_stat_rows,
    cooccurrence_pairs,
    persist_term_stats,
    select_evidence,
)
from metaprofile.new_tech_discovery.services.signal_metrics import (
    TermStats,
    apply_source_weights,
    build_term_stats,
    build_windows,
    burst_score,
    coherence_score,
    diversity_score,
    novelty_score,
    prime_jieba,
    tokenize,
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
    is_tech_term: bool = False


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
        2. 拉取 lookback_start..period_to 全期语料（8 源,domain→industry 过滤）
        3. build_term_stats → 每候选词项的窗口/源计数统计
        4. 逐项算 burst/novelty/diversity/velocity/coherence → strength
        5. 自适应阈值 + burst_theta 过滤 → 弱信号
        6. 证据链回填（A4）:evidence_doc_ids + related_*_ids + 真共现边（A5）
        7. term_stats 持久化（A3）+ 落 WeakSignalORM（signal_id 幂等）
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
        docs = await self._load_corpus(lookback_start, period_to, db, domain)

        # 技术词典(概念名/域名词,2026-10-15 词质量治理):命中词 strength 加成;
        # 注入 jieba 必须在 build_term_stats(切词)之前——技术整词不被切碎
        tech_dict = await self._load_tech_dict(db)
        prime_jieba(tech_dict)
        term_stats = build_term_stats(docs, windows, min_df=2)
        stats_by_term = {ts.term: ts for ts in term_stats}

        candidates: list[dict] = []
        for ts in term_stats:
            df_current = (
                sum(ts.df_by_window[i] for i in current_idx) if current_idx else 0
            )
            df_history = [ts.df_by_window[i] for i in history_idx]
            burst = burst_score(df_current, df_history) if df_history else 0.0
            seen = sum(1 for i in history_idx if ts.df_by_window[i] > 0)
            novelty = novelty_score(seen, n_history)
            diversity = diversity_score(apply_source_weights(ts.df_by_source))
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
            is_tech_term = ts.term in tech_dict
            if is_tech_term:
                strength = min(1.0, strength + ws.tech_term_boost)
            else:
                strength *= ws.nontech_discount
            candidates.append({
                "term": ts.term, "strength": strength, "burst": burst,
                "novelty": novelty, "diversity": diversity,
                "velocity": velocity, "coherence": coherence,
                "is_entity": ts.is_entity, "df_current": df_current,
                "is_tech_term": is_tech_term,
            })

        if not candidates:
            return []

        threshold = await self._compute_threshold(db, domain)

        signals: list[WeakSignal] = []
        for c in candidates:
            # 双池门槛(2026-10-15 词质量治理):非技术词典词须突现极强才入围,
            # 防"反复/2026/两市"类泛词靠 novelty/diversity 空转刷分
            if not c.get("is_tech_term") and c["burst"] < ws.nontech_burst_gate:
                continue
            if c["strength"] < threshold and c["burst"] < ws.burst_theta:
                continue
            kw = [c["term"]]
            sig_id = "WS-" + hashlib.md5("|".join(kw).encode()).hexdigest()[:16]
            signals.append(WeakSignal(
                signal_id=sig_id, keywords=kw,
                related_tech_ids=[], related_org_ids=[], related_person_ids=[],
                strength=round(c["strength"], 4),
                novelty=round(c["novelty"], 4),
                coherence=round(c["coherence"], 4),
                diversity=round(c["diversity"], 4),
                velocity=round(c["velocity"], 4),
                period_from=period_from, period_to=period_to,
                evidence_doc_ids=[],
                is_tech_term=c.get("is_tech_term", False),
            ))

        # 单轮信号上限(首轮自适应阈值落地板时存活可达数千 → 边表爆炸);
        # 排序=技术词典词优先占席,泛词只能垫底(词质量治理终刀)
        if len(signals) > ws.max_signals:
            signals.sort(
                key=lambda s: (s.is_tech_term, s.strength, s.velocity),
                reverse=True,
            )
            dropped = len(signals) - ws.max_signals
            signals = signals[:ws.max_signals]
            logger.info("weak_signal_capped", kept=ws.max_signals, dropped=dropped)

        # 先删后插(审查 H3):signal_id=md5(keywords) 不含周期/域,窗口重叠的
        # 重扫同词必撞 unique → 整任务回滚。分块 IN 防参数超 32767(真跑
        # 百万候选踩过);显式 DELETE 先于 flush 的 INSERT 执行。
        # 边表 signal_id 为裸串无 FK,由各写入方自清理。
        if signals:
            sids = [s.signal_id for s in signals]
            for i in range(0, len(sids), 1000):
                await db.execute(
                    sa_delete(WeakSignalORM).where(
                        WeakSignalORM.signal_id.in_(sids[i:i + 1000])
                    )
                )

        orm_by_sid: dict[str, WeakSignalORM] = {}
        for sig in signals:
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
            orm_by_sid[sig.signal_id] = orm
        await db.flush()

        # ── A4:证据链回填 ──
        await self._link_evidence(db, signals, stats_by_term, docs, ws, orm_by_sid)
        # ── A5:同文档真共现边 ──
        if ws.cooccurrence_edges:
            await self._write_cooccurrence_edges(db, signals, docs)
        # ── A3:term_stats 持久化 ──
        if ws.persist_term_stats:
            rows = build_term_stat_rows(
                self._top_stats(term_stats, ws.term_stats_max_terms), windows,
            )
            await persist_term_stats(db, rows)

        logger.info(
            "weak_signal_extracted", count=len(signals), threshold=threshold,
            candidates=len(candidates),
        )
        return signals

    @staticmethod
    def _top_stats(term_stats: list[TermStats], cap: int) -> list[TermStats]:
        if len(term_stats) <= cap:
            return term_stats
        ranked = sorted(
            term_stats, key=lambda t: sum(t.df_by_window), reverse=True,
        )
        return ranked[:cap]

    @staticmethod
    async def _load_tech_dict(db: AsyncSession) -> set[str]:
        """技术词典:tech_profile 全部概念/域中英文名(词质量治理加权用)。"""
        from metaprofile.profile_tech.domain.orm_models import TechProfileORM

        rows = (await db.execute(
            select(TechProfileORM.tech_name_cn, TechProfileORM.tech_name_en,
                   TechProfileORM.cluster_terms)
        )).all()
        names: set[str] = set()
        for cn, en, cluster in rows:
            for n in (cn, en):
                if n and len(n) >= 2:
                    names.add(n)
            for t in (cluster or []):
                if t and len(t) >= 2:
                    names.add(t)
        return names

    async def _link_evidence(self, db, signals, stats_by_term, docs, ws,
                             orm_by_sid: dict) -> None:
        """每信号:evidence_doc_ids(最近 N 篇)+ evidence 文档实体 → 画像 id。"""
        if not signals:
            return
        docs_by_id = {d.doc_id: d for d in docs}
        linker = EntityLinker(db)
        for sig in signals:
            ts = stats_by_term.get(sig.keywords[0])
            if ts is None or not ts.doc_ids:
                continue
            ev = select_evidence(ts.doc_ids, cap=ws.evidence_docs_cap)
            sig.evidence_doc_ids = ev
            ent_names: list[str] = []
            for did in ev:
                doc = docs_by_id.get(did)
                if doc is not None:
                    ent_names.extend(doc.entities or [])
            if ent_names:
                sig.related_org_ids = await linker.link_orgs(
                    ent_names, cap=ws.related_cap,
                )
                sig.related_person_ids = await linker.link_persons(
                    ent_names, cap=ws.related_cap,
                )
                sig.related_tech_ids = await linker.link_techs(
                    sig.keywords + ent_names, cap=ws.related_cap,
                )
            orm = orm_by_sid.get(sig.signal_id)
            if orm is not None:
                orm.evidence_doc_ids = sig.evidence_doc_ids
                orm.related_org_ids = sig.related_org_ids
                orm.related_person_ids = sig.related_person_ids
                orm.related_tech_ids = sig.related_tech_ids
        await db.flush()

    async def _write_cooccurrence_edges(self, db, signals, docs) -> None:
        """同文档共现的信号词对 → signal↔signal 边(替换 REST 启发式,G6)。"""
        if len(signals) < 2:
            return
        sig_by_term = {s.keywords[0]: s.signal_id for s in signals}
        signal_terms = set(sig_by_term)
        # 生成器惰性求值(审查 M5):避免 16 万文档的词集全量物化
        docs_terms = (
            set(tokenize(d.text)) | set(d.entities or []) for d in docs
        )
        weights = cooccurrence_pairs(docs_terms, signal_terms)
        if not weights:
            return
        sig_ids = list({sid for sid in sig_by_term.values()})
        for i in range(0, len(sig_ids), 1000):
            await db.execute(
                sa_delete(SignalNetworkEdgeORM).where(
                    SignalNetworkEdgeORM.signal_id.in_(sig_ids[i:i + 1000]),
                    SignalNetworkEdgeORM.edge_type == "co_occurrence",
                )
            )
        for (a, b), w in weights.items():
            db.add(SignalNetworkEdgeORM(
                signal_id=sig_by_term[a], source_id=sig_by_term[a],
                source_type="signal", target_id=sig_by_term[b],
                target_type="signal", edge_type="co_occurrence",
                weight=float(w),
            ))
        await db.flush()

    async def _load_corpus(self, start: date, end: date, db: AsyncSession,
                           domain: str | None = None):
        if self._loader is None:
            from metaprofile.new_tech_discovery.services.corpus_loader import CorpusLoader
            self._loader = CorpusLoader()
        # 源白名单走 settings(默认排除 market/key_events 消费噪声,C 治理)
        sources = [s for s in settings.weak_signal.source_list]
        docs = []
        for source in sources:
            docs.extend(
                await self._loader.load(
                    self._db_connection_id, source, start, end,
                    industry=domain, session=db,
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
