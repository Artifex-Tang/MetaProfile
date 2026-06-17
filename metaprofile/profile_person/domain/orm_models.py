"""
人员画像 ORM 模型。

字段与《实体画像数据规范》人员节一一对应。
扩展属性（多值）拆分到独立表，主表只存基本属性与可索引字段。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from metaprofile.shared.db.base import Base, TimestampMixin


class PersonProfileORM(Base, TimestampMixin):
    """人员画像主表（基本属性）。"""

    __tablename__ = "person_profile"

    person_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_cn: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gender: Mapped[str] = mapped_column(String(8), nullable=False)
    avatar: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    nationality: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    age: Mapped[int | None] = mapped_column(Integer)
    birthplace: Mapped[str | None] = mapped_column(String(255))
    ethnicity: Mapped[str | None] = mapped_column(String(64))
    current_residence: Mapped[str | None] = mapped_column(String(255))
    current_org: Mapped[str | None] = mapped_column(String(512))
    current_enterprise: Mapped[str | None] = mapped_column(String(512))
    current_military_unit: Mapped[str | None] = mapped_column(String(512))
    current_position: Mapped[list] = mapped_column(JSON, nullable=False)
    highest_degree: Mapped[str | None] = mapped_column(String(16))
    person_category: Mapped[str | None] = mapped_column(String(16))
    professional_domains: Mapped[list] = mapped_column(JSON, nullable=False)
    professional_skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    social_media: Mapped[str | None] = mapped_column(String(512))
    personality_traits: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    hobbies: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    management_philosophy: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    remark: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 质量评分（抽取管线写入）
    veracity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timeliness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    data_as_of: Mapped[date | None] = mapped_column(Date)

    educations: Mapped[list["PersonEducationORM"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    careers: Mapped[list["PersonCareerORM"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    awards: Mapped[list["PersonAwardORM"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    academic_outputs: Mapped[list["PersonAcademicOutputORM"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    opinions: Mapped[list["PersonOpinionORM"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["PersonReviewORM"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    tech_focuses: Mapped[list["PersonFocusORM"]] = relationship(
        "PersonFocusORM",
        primaryjoin="and_(PersonFocusORM.person_id==PersonProfileORM.person_id, PersonFocusORM.focus_type=='tech')",
        cascade="all, delete-orphan",
        overlaps="reform_focuses",
    )
    reform_focuses: Mapped[list["PersonFocusORM"]] = relationship(
        "PersonFocusORM",
        primaryjoin="and_(PersonFocusORM.person_id==PersonProfileORM.person_id, PersonFocusORM.focus_type=='reform')",
        cascade="all, delete-orphan",
        overlaps="tech_focuses",
    )


class PersonEducationORM(Base, TimestampMixin):
    __tablename__ = "person_education"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("person_profile.person_id", ondelete="CASCADE"), index=True
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    degree_date: Mapped[date | None] = mapped_column(Date)
    degree: Mapped[str | None] = mapped_column(String(16))
    school: Mapped[str | None] = mapped_column(String(512))
    major: Mapped[str | None] = mapped_column(String(255))

    person: Mapped[PersonProfileORM] = relationship(back_populates="educations")


class PersonCareerORM(Base, TimestampMixin):
    __tablename__ = "person_career"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("person_profile.person_id", ondelete="CASCADE"), index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    org: Mapped[str] = mapped_column(String(512), nullable=False)
    enterprise: Mapped[str | None] = mapped_column(String(512))
    military_unit: Mapped[str | None] = mapped_column(String(512))
    position: Mapped[str | None] = mapped_column(String(255))

    person: Mapped[PersonProfileORM] = relationship(back_populates="careers")


class PersonAwardORM(Base, TimestampMixin):
    __tablename__ = "person_award"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("person_profile.person_id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str | None] = mapped_column(Text)

    person: Mapped[PersonProfileORM] = relationship(back_populates="awards")


class PersonAcademicOutputORM(Base, TimestampMixin):
    __tablename__ = "person_academic_output"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("person_profile.person_id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(512))
    form: Mapped[str | None] = mapped_column(String(16))
    publish_date: Mapped[date | None] = mapped_column(Date)
    rank: Mapped[str | None] = mapped_column(String(16))
    tech_domain: Mapped[str | None] = mapped_column(String(255))
    collaborators: Mapped[list] = mapped_column(JSON, default=list)
    citations: Mapped[int | None] = mapped_column(Integer)
    is_representative: Mapped[bool | None] = mapped_column(Boolean)

    person: Mapped[PersonProfileORM] = relationship(back_populates="academic_outputs")


class PersonOpinionORM(Base, TimestampMixin):
    __tablename__ = "person_opinion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("person_profile.person_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    publish_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    occasion: Mapped[str | None] = mapped_column(String(255))
    main_points: Mapped[str | None] = mapped_column(Text)
    target_keywords: Mapped[list] = mapped_column(JSON, default=list)

    person: Mapped[PersonProfileORM] = relationship(back_populates="opinions")


class PersonReviewORM(Base, TimestampMixin):
    __tablename__ = "person_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("person_profile.person_id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str | None] = mapped_column(Text)
    review_org: Mapped[str | None] = mapped_column(String(255))
    review_enterprise: Mapped[str | None] = mapped_column(String(255))
    review_person: Mapped[str | None] = mapped_column(String(255))
    review_type: Mapped[str | None] = mapped_column(String(32))
    review_date: Mapped[date | None] = mapped_column(Date)

    person: Mapped[PersonProfileORM] = relationship(back_populates="reviews")


class PersonFocusORM(Base, TimestampMixin):
    """技术关注重点 / 政策改革重点（用 focus_type 区分）。"""

    __tablename__ = "person_focus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("person_profile.person_id", ondelete="CASCADE"), index=True
    )
    focus_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'tech' | 'reform'
    content: Mapped[list] = mapped_column(JSON, default=list)
    consistency_with_policy: Mapped[str | None] = mapped_column(Text)
    potential_impact: Mapped[list] = mapped_column(JSON, default=list)


from metaprofile.shared.db.orm_models import EntityChangeLogORM

__all__ = ["EntityChangeLogORM"]
