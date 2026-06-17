"""
项目画像 ORM 模型。

字段与《实体画像数据规范》项目节一一对应。
多值列表字段存为 JSON；扩展属性拆分到独立表。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from metaprofile.shared.db.base import Base, TimestampMixin


class ProjectProfileORM(Base, TimestampMixin):
    """项目画像主表（基本属性）。"""

    __tablename__ = "project_profile"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_cn: Mapped[list] = mapped_column(JSON, nullable=False)
    name_en: Mapped[list] = mapped_column(JSON, nullable=False)
    name_other: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tech_domain: Mapped[list] = mapped_column(JSON, nullable=False)
    sub_tech_domain: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    cancel_date: Mapped[date | None] = mapped_column(Date)
    finish_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    budget_activities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    project_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    main_orgs: Mapped[list] = mapped_column(JSON, nullable=False)
    undertaking_orgs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    undertaking_enterprises: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    managers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    researchers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    background: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    research_goal: Mapped[str | None] = mapped_column(Text)
    research_content: Mapped[list] = mapped_column(JSON, nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    progress: Mapped[list] = mapped_column(JSON, nullable=False)
    application_prospect: Mapped[str | None] = mapped_column(Text)
    key_dates: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    total_budget_million_usd: Mapped[float | None] = mapped_column(Numeric(18, 4))
    invested_million_usd: Mapped[float | None] = mapped_column(Numeric(18, 4))
    parent_package_name: Mapped[str | None] = mapped_column(String(512))
    previous_phase_name: Mapped[str | None] = mapped_column(String(512))

    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 质量评分（抽取管线写入）
    veracity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timeliness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    data_as_of: Mapped[date | None] = mapped_column(Date)

    histories: Mapped[list["ProjectHistoryORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["ProjectBudgetORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    outputs: Mapped[list["ProjectOutputORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectHistoryORM(Base, TimestampMixin):
    __tablename__ = "project_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("project_profile.project_id", ondelete="CASCADE"),
        index=True,
    )
    change_date: Mapped[date | None] = mapped_column(Date)
    change_description: Mapped[str | None] = mapped_column(Text)

    project: Mapped[ProjectProfileORM] = relationship(back_populates="histories")


class ProjectBudgetORM(Base, TimestampMixin):
    __tablename__ = "project_budget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("project_profile.project_id", ondelete="CASCADE"),
        index=True,
    )
    budget_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)

    project: Mapped[ProjectProfileORM] = relationship(back_populates="budgets")


class ProjectOutputORM(Base, TimestampMixin):
    __tablename__ = "project_output"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("project_profile.project_id", ondelete="CASCADE"),
        index=True,
    )
    name_history: Mapped[str | None] = mapped_column(Text)
    formed_at: Mapped[date | None] = mapped_column(Date)
    tech_domains: Mapped[list] = mapped_column(JSON, default=list)
    owner_orgs: Mapped[list] = mapped_column(JSON, default=list)
    related_projects: Mapped[list] = mapped_column(JSON, default=list)
    attachments: Mapped[list] = mapped_column(JSON, default=list)

    project: Mapped[ProjectProfileORM] = relationship(back_populates="outputs")


from metaprofile.shared.db.orm_models import EntityChangeLogORM

__all__ = ["EntityChangeLogORM"]
