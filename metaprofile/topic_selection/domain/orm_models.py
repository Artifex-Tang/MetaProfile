"""选题服务 ORM 模型：选题候选存储。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from metaprofile.shared.db.base import Base, TimestampMixin


class TopicCandidateORM(Base, TimestampMixin):
    """选题候选记录。"""

    __tablename__ = "topic_candidate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str | None] = mapped_column(String(16))  # 如 2026Q1

    related_tech_ids: Mapped[list] = mapped_column(JSON, default=list)
    related_org_ids: Mapped[list] = mapped_column(JSON, default=list)
    related_project_ids: Mapped[list] = mapped_column(JSON, default=list)
    related_policy_refs: Mapped[list] = mapped_column(JSON, default=list)

    # 五策略分
    score_hot: Mapped[float] = mapped_column(Float, default=0.0)
    score_policy: Mapped[float] = mapped_column(Float, default=0.0)
    score_impact: Mapped[float] = mapped_column(Float, default=0.0)
    score_dedup: Mapped[float] = mapped_column(Float, default=0.0)
    score_llm_gen: Mapped[float] = mapped_column(Float, default=0.0)

    # LLM 评审 4 维度
    review_novelty: Mapped[float] = mapped_column(Float, default=0.0)
    review_importance: Mapped[float] = mapped_column(Float, default=0.0)
    review_feasibility: Mapped[float] = mapped_column(Float, default=0.0)
    review_expression: Mapped[float] = mapped_column(Float, default=0.0)
    review_evidence: Mapped[str | None] = mapped_column(Text)

    final_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/accepted/rejected/revised


class TopicFeedbackORM(Base, TimestampMixin):
    """选题反馈记录（用于在线学习）。"""

    __tablename__ = "topic_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    rating: Mapped[str] = mapped_column(String(16), nullable=False)  # accept/reject/revise
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comments: Mapped[str | None] = mapped_column(Text)
    operator: Mapped[str] = mapped_column(String(64), nullable=False)
