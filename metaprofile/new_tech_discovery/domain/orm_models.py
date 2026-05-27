"""新技术发现 ORM 模型：弱信号识别结果存储。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, JSON, String, Text
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
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # tech/org/person
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False)  # co_occurrence/citation/funding
    weight: Mapped[float] = mapped_column(Float, default=1.0)
