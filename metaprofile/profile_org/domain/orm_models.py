"""
机构画像 ORM 模型。

字段与《实体画像数据规范》机构节一一对应。
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
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from metaprofile.shared.db.base import Base, TimestampMixin


class OrgProfileORM(Base, TimestampMixin):
    """机构画像主表（基本属性）。"""

    __tablename__ = "org_profile"

    org_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_cn: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name_other: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    founded_date: Mapped[date | None] = mapped_column(Date)
    dissolved_date: Mapped[date | None] = mapped_column(Date)
    operating_years: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    website: Mapped[str | None] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    org_types: Mapped[list] = mapped_column(JSON, nullable=False)
    nature: Mapped[str] = mapped_column(String(32), nullable=False)
    function: Mapped[str] = mapped_column(Text, nullable=False)
    scale: Mapped[int | None] = mapped_column(Integer)
    tech_domains: Mapped[list] = mapped_column(JSON, nullable=False)
    predecessor_names: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    departments: Mapped[str | None] = mapped_column(Text)
    strategic_plans: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    evaluation_report: Mapped[str | None] = mapped_column(Text)
    new_key_projects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)

    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    histories: Mapped[list["OrgHistoryORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    affiliations: Mapped[list["OrgAffiliationORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    awards: Mapped[list["OrgAwardORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["OrgBudgetORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    fundings_received: Mapped[list["OrgFundingReceivedORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    outputs: Mapped[list["OrgOutputORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["OrgReviewORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    addresses: Mapped[list["OrgAddressORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    activities: Mapped[list["OrgActivityORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )
    team: Mapped["OrgTeamORM | None"] = relationship(
        back_populates="org", cascade="all, delete-orphan", uselist=False
    )
    facilities: Mapped[list["OrgFacilityORM"]] = relationship(
        back_populates="org", cascade="all, delete-orphan"
    )


class OrgHistoryORM(Base, TimestampMixin):
    __tablename__ = "org_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    change_date: Mapped[date] = mapped_column(Date, nullable=False)
    change_description: Mapped[str] = mapped_column(Text, nullable=False)

    org: Mapped[OrgProfileORM] = relationship(back_populates="histories")


class OrgAffiliationORM(Base, TimestampMixin):
    __tablename__ = "org_affiliation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    change_date: Mapped[date | None] = mapped_column(Date)
    parent_name: Mapped[str] = mapped_column(String(512), nullable=False)

    org: Mapped[OrgProfileORM] = relationship(back_populates="affiliations")


class OrgAwardORM(Base, TimestampMixin):
    __tablename__ = "org_award"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(String(512))
    reason: Mapped[str | None] = mapped_column(Text)
    award_date: Mapped[date | None] = mapped_column(Date)
    level: Mapped[str | None] = mapped_column(String(64))
    award_type: Mapped[str | None] = mapped_column(String(64))

    org: Mapped[OrgProfileORM] = relationship(back_populates="awards")


class OrgBudgetORM(Base, TimestampMixin):
    __tablename__ = "org_budget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    funder_name: Mapped[str | None] = mapped_column(String(512))
    budget_date: Mapped[date | None] = mapped_column(Date)
    amount_usd: Mapped[float | None] = mapped_column(Numeric(18, 4))

    org: Mapped[OrgProfileORM] = relationship(back_populates="budgets")


class OrgFundingReceivedORM(Base, TimestampMixin):
    __tablename__ = "org_funding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    funder_name: Mapped[str | None] = mapped_column(String(512))
    fund_date: Mapped[date | None] = mapped_column(Date)
    amount_or_equipment: Mapped[str | None] = mapped_column(Text)

    org: Mapped[OrgProfileORM] = relationship(back_populates="fundings_received")


class OrgOutputORM(Base, TimestampMixin):
    __tablename__ = "org_output"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(512))
    form: Mapped[str | None] = mapped_column(String(64))
    author: Mapped[str | None] = mapped_column(String(255))
    publish_date: Mapped[date | None] = mapped_column(Date)
    attachment: Mapped[str | None] = mapped_column(String(512))

    org: Mapped[OrgProfileORM] = relationship(back_populates="outputs")


class OrgReviewORM(Base, TimestampMixin):
    __tablename__ = "org_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str | None] = mapped_column(Text)
    review_org: Mapped[str | None] = mapped_column(String(255))
    review_person: Mapped[str | None] = mapped_column(String(255))
    review_type: Mapped[str | None] = mapped_column(String(32))
    review_date: Mapped[date | None] = mapped_column(Date)

    org: Mapped[OrgProfileORM] = relationship(back_populates="reviews")


class OrgAddressORM(Base, TimestampMixin):
    __tablename__ = "org_address"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    address: Mapped[str] = mapped_column(Text, nullable=False)
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)

    org: Mapped[OrgProfileORM] = relationship(back_populates="addresses")


class OrgActivityORM(Base, TimestampMixin):
    __tablename__ = "org_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    activity_type: Mapped[str | None] = mapped_column(String(64))
    content: Mapped[str | None] = mapped_column(Text)
    activity_date: Mapped[date | None] = mapped_column(Date)
    locations: Mapped[list] = mapped_column(JSON, default=list)

    org: Mapped[OrgProfileORM] = relationship(back_populates="activities")


class OrgTeamORM(Base, TimestampMixin):
    __tablename__ = "org_team"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("org_profile.org_id", ondelete="CASCADE"),
        index=True,
        unique=True,
    )
    top_talents: Mapped[list] = mapped_column(JSON, default=list)
    award_winners: Mapped[list] = mapped_column(JSON, default=list)
    team_size: Mapped[int | None] = mapped_column(Integer)
    talent_type: Mapped[str | None] = mapped_column(String(128))

    org: Mapped[OrgProfileORM] = relationship(back_populates="team")


class OrgFacilityORM(Base, TimestampMixin):
    __tablename__ = "org_facility"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("org_profile.org_id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(512))
    purpose: Mapped[str | None] = mapped_column(Text)
    experiment_status: Mapped[str | None] = mapped_column(String(64))
    launch_date: Mapped[date | None] = mapped_column(Date)
    construction_cost_wan_usd: Mapped[float | None] = mapped_column(Numeric(18, 4))

    org: Mapped[OrgProfileORM] = relationship(back_populates="facilities")


from metaprofile.shared.db.orm_models import EntityChangeLogORM

__all__ = ["EntityChangeLogORM"]
