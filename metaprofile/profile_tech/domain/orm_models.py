"""
技术画像 ORM 模型。

字段与《实体画像数据规范》技术节一一对应。
扩展属性（多值）拆分到独立表，主表只存基本属性。
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


class TechProfileORM(Base, TimestampMixin):
    """技术画像主表（基本属性）。"""

    __tablename__ = "tech_profile"

    tech_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tech_name_cn: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tech_name_en: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tech_name_other: Mapped[str | None] = mapped_column(String(255))
    tech_domain: Mapped[list] = mapped_column(JSON, nullable=False)
    invention_date: Mapped[date | None] = mapped_column(Date)
    application_date: Mapped[date | None] = mapped_column(Date)
    tech_summary: Mapped[str] = mapped_column(Text, nullable=False)
    dev_goal: Mapped[str | None] = mapped_column(Text)
    project_layout: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    key_points: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    transformation_status: Mapped[str | None] = mapped_column(Text)
    basic_research_status: Mapped[str | None] = mapped_column(Text)
    autonomy_capability: Mapped[str | None] = mapped_column(Text)
    industrial_capability: Mapped[str | None] = mapped_column(Text)
    tech_advantages: Mapped[str | None] = mapped_column(Text)
    current_status: Mapped[str] = mapped_column(Text, nullable=False)
    trend: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)

    # 元数据
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 扩展属性关联
    dev_milestones: Mapped[list["TechDevMilestoneORM"]] = relationship(
        back_populates="tech", cascade="all, delete-orphan"
    )
    review_impacts: Mapped[list["TechReviewImpactORM"]] = relationship(
        back_populates="tech", cascade="all, delete-orphan"
    )
    fundings: Mapped[list["TechFundingORM"]] = relationship(
        back_populates="tech", cascade="all, delete-orphan"
    )
    academic_outputs: Mapped[list["TechAcademicOutputORM"]] = relationship(
        back_populates="tech", cascade="all, delete-orphan"
    )
    experiments: Mapped[list["TechExperimentORM"]] = relationship(
        back_populates="tech", cascade="all, delete-orphan"
    )


class TechDevMilestoneORM(Base, TimestampMixin):
    __tablename__ = "tech_dev_milestone"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tech_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tech_profile.tech_id", ondelete="CASCADE"), index=True
    )
    milestone_date: Mapped[date | None] = mapped_column(Date)
    milestone_name: Mapped[str | None] = mapped_column(String(512))
    contributor_keywords: Mapped[list] = mapped_column(JSON, default=list)
    milestone_content: Mapped[str | None] = mapped_column(Text)

    tech: Mapped[TechProfileORM] = relationship(back_populates="dev_milestones")


class TechReviewImpactORM(Base, TimestampMixin):
    __tablename__ = "tech_review_impact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tech_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tech_profile.tech_id", ondelete="CASCADE"), index=True
    )
    review_date: Mapped[date | None] = mapped_column(Date)
    review_org: Mapped[str | None] = mapped_column(String(255))
    review_person: Mapped[str | None] = mapped_column(String(255))
    review_content: Mapped[str | None] = mapped_column(Text)
    review_type: Mapped[str | None] = mapped_column(String(32))

    tech: Mapped[TechProfileORM] = relationship(back_populates="review_impacts")


class TechFundingORM(Base, TimestampMixin):
    __tablename__ = "tech_funding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tech_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tech_profile.tech_id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    source: Mapped[str | None] = mapped_column(String(255))

    tech: Mapped[TechProfileORM] = relationship(back_populates="fundings")


class TechAcademicOutputORM(Base, TimestampMixin):
    __tablename__ = "tech_academic_output"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tech_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tech_profile.tech_id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(512))
    publish_date: Mapped[date | None] = mapped_column(Date)
    subject_keywords: Mapped[list] = mapped_column(JSON, default=list)
    image: Mapped[str | None] = mapped_column(String(255))

    tech: Mapped[TechProfileORM] = relationship(back_populates="academic_outputs")


class TechExperimentORM(Base, TimestampMixin):
    __tablename__ = "tech_experiment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tech_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tech_profile.tech_id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str | None] = mapped_column(Text)
    experiment_date: Mapped[date | None] = mapped_column(Date)
    result: Mapped[str | None] = mapped_column(Text)
    subject_keywords: Mapped[list] = mapped_column(JSON, default=list)
    image: Mapped[str | None] = mapped_column(String(255))

    tech: Mapped[TechProfileORM] = relationship(back_populates="experiments")


from metaprofile.shared.db.orm_models import EntityChangeLogORM

__all__ = ["EntityChangeLogORM"]
