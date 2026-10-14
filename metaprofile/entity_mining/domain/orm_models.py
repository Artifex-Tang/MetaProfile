"""实体挖掘 ORM(Phase D):归一/消歧/分类建议。"""
from __future__ import annotations

from sqlalchemy import JSON, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from metaprofile.shared.db.base import Base, TimestampMixin


class EntityResolutionSuggestionORM(Base, TimestampMixin):
    """实体解析建议(只建议不自动合并,人工确认后应用)。

    suggestion_kind: ror_match(机构 ROR 归一) | author_dedup(作者消歧)
                     | project_classify(项目 IPC 域分类)
    """

    __tablename__ = "entity_resolution_suggestion"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "raw_name", "suggestion_kind",
            name="uq_ers_entity_kind_name",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    raw_name: Mapped[str] = mapped_column(String(512), nullable=False)
    suggestion_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    matched_id: Mapped[str | None] = mapped_column(String(128))
    matched_name: Mapped[str | None] = mapped_column(String(512))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
