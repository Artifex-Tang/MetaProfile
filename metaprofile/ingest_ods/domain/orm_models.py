"""ingest_ods 域 ORM：DB 连接注册 + 抽取 staging + 关系 staging + 错误。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from metaprofile.shared.db.base import Base, TimestampMixin


class DBConnectionORM(Base, TimestampMixin):
    """外部 DB 连接注册（Doris 云/本地）。密码加密存 password_enc。"""
    __tablename__ = "db_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    dialect: Mapped[str] = mapped_column(String(16), nullable=False, default="doris")
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    password_enc: Mapped[str] = mapped_column(Text, nullable=False)
    charset: Mapped[str] = mapped_column(String(32), nullable=False, default="utf8mb4")
    pool_size: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IngestRawORM(Base, TimestampMixin):
    """抽取 staging：逐源行贡献 + provenance。"""
    __tablename__ = "ingest_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_key: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection_tasks.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")


class RelationStagingORM(Base, TimestampMixin):
    """关系 staging：内容挖掘产出的三元组（审计 + 写 Neo4j 去重）。"""
    __tablename__ = "relation_staging"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection_tasks.id"), nullable=False, index=True)
    subject_name: Mapped[str] = mapped_column(String(512), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    written: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class IngestErrorORM(Base, TimestampMixin):
    """抽取错误（单批单行失败，不阻塞整任务）。"""
    __tablename__ = "ingest_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection_tasks.id"), nullable=False, index=True)
    source_table: Mapped[str | None] = mapped_column(String(128))
    source_id: Mapped[str | None] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    error_msg: Mapped[str] = mapped_column(Text, nullable=False)


class TechEvidenceORM(Base, TimestampMixin):
    """技术概念证据：每条 tech 概念的逐源抽取证据（provenance + snippet）。"""
    __tablename__ = "tech_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tech_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tech_profile.tech_id", ondelete="CASCADE"), index=True
    )
    source_doc_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    __table_args__ = (
        UniqueConstraint("tech_id", "source_doc_id", "source_table", name="uq_tech_evidence"),
    )
