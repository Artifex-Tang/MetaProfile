"""扫描监测 ORM 模型：前沿技术识别结果存储。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from metaprofile.shared.db.base import Base, TimestampMixin


class FrontierTechORM(Base, TimestampMixin):
    """前沿技术候选识别结果。每次扫描任务产生一批记录。"""

    __tablename__ = "frontier_tech"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_task_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    tech_id: Mapped[str | None] = mapped_column(String(64), index=True)  # profile_tech 画像ID
    tech_name: Mapped[str] = mapped_column(String(256), nullable=False)
    tech_domain: Mapped[list] = mapped_column(JSON, default=list)
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)

    # 五维信号得分 [0,1]
    burst_score: Mapped[float] = mapped_column(Float, default=0.0)
    patent_score: Mapped[float] = mapped_column(Float, default=0.0)
    citation_score: Mapped[float] = mapped_column(Float, default=0.0)
    invest_score: Mapped[float] = mapped_column(Float, default=0.0)
    policy_score: Mapped[float] = mapped_column(Float, default=0.0)
    fusion_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)

    # LLM Agent 验证
    llm_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_verdict: Mapped[str | None] = mapped_column(String(16))  # 是/否/待定
    llm_evidence: Mapped[str | None] = mapped_column(Text)

    # TRL 标注
    trl_level: Mapped[int | None] = mapped_column(Integer)  # 1-9

    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/validated/rejected


class ScanAlertORM(Base, TimestampMixin):
    """前沿技术告警记录。"""

    __tablename__ = "scan_alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    frontier_tech_id: Mapped[int | None] = mapped_column(Integer, index=True)
    tech_name: Mapped[str] = mapped_column(String(256), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)  # burst/trl_upgrade/org_layout
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info/warn/critical
    message: Mapped[str] = mapped_column(Text, nullable=False)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
