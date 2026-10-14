"""新技术发现 ORM 模型：弱信号识别结果存储。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Date, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from metaprofile.shared.db.base import Base, TimestampMixin


class WeakSignalORM(Base, TimestampMixin):
    """弱信号识别结果。"""

    __tablename__ = "weak_signal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    related_tech_ids: Mapped[list] = mapped_column(JSON, default=list)
    related_org_ids: Mapped[list] = mapped_column(JSON, default=list)
    related_person_ids: Mapped[list] = mapped_column(JSON, default=list)
    evidence_doc_ids: Mapped[list] = mapped_column(JSON, default=list)

    strength: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    novelty: Mapped[float] = mapped_column(Float, default=0.0)
    coherence: Mapped[float] = mapped_column(Float, default=0.0)
    diversity: Mapped[float] = mapped_column(Float, default=0.0)
    velocity: Mapped[float] = mapped_column(Float, default=0.0)

    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")  # active/archived


class SignalNetworkEdgeORM(Base, TimestampMixin):
    """弱信号关联网络边。"""

    __tablename__ = "signal_network_edge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # tech/org/person/signal
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # co_occurrence/citation/funding
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class TermStatORM(Base, TimestampMixin):
    """术语窗口计数持久化(Phase A3):窗口×源×术语 df/tf。

    source="*" 表示全源合并行(当前实现);分源行留作扩展。
    修 G7(无时序存储,每次重算)与 G8(coherence presence→计数)。
    """

    __tablename__ = "term_stats"
    __table_args__ = (
        UniqueConstraint(
            "window_month", "source", "term", "term_kind",
            name="uq_term_stats",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    window_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="*")
    term: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    term_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="term")
    df: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tf: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TechEmergenceIndicatorORM(Base, TimestampMixin):
    """新兴指标(Phase B):对象×窗口×指标 JSONB。

    object_type: ipc_domain(ipc:G06T) | ipc_pair(G06N|G06T)
    metrics: {patents,applicants,active_entities,new_entrant_ratio,doubling_time,
              tem_share,tem_growth,tem_quadrant,s_curve_stage,haupt_ratio,
              salton,first_seen,is_new_pair,salton_rising}
    """

    __tablename__ = "tech_emergence_indicator"
    __table_args__ = (
        UniqueConstraint(
            "object_type", "object_id", "window_month",
            name="uq_emergence_object_window",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    window_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class DisruptionAssessmentORM(Base, TimestampMixin):
    """颠覆性评估(Phase C):对象×窗口 组件分+合分+LLM rubric 判定。"""

    __tablename__ = "disruption_assessment"
    __table_args__ = (
        UniqueConstraint(
            "object_type", "object_id", "window_month",
            name="uq_disruption_object_window",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    window_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    novelty_comb: Mapped[float] = mapped_column(Float, default=0.0)
    growth: Mapped[float] = mapped_column(Float, default=0.0)
    new_entrant: Mapped[float] = mapped_column(Float, default=0.0)
    small_team: Mapped[float] = mapped_column(Float, default=0.0)
    term_novelty: Mapped[float] = mapped_column(Float, default=0.0)
    disrupt_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    llm_verdict: Mapped[str] = mapped_column(String(16), default="pending")
    llm_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    llm_evidence: Mapped[str | None] = mapped_column(Text)
