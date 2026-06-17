"""ingest_ods: db_connections + staging 表 + profile 主表质量评分列

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect
    insp = inspect(op.get_bind())

    if not insp.has_table("db_connections"):
        op.create_table(
            "db_connections",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(128), nullable=False, unique=True),
            sa.Column("dialect", sa.String(16), nullable=False, server_default="doris"),
            sa.Column("host", sa.String(255), nullable=False),
            sa.Column("port", sa.Integer, nullable=False),
            sa.Column("database", sa.String(128), nullable=False),
            sa.Column("username", sa.String(128), nullable=False),
            sa.Column("password_enc", sa.Text, nullable=False),
            sa.Column("charset", sa.String(32), nullable=False, server_default="utf8mb4"),
            sa.Column("pool_size", sa.Integer, nullable=False, server_default="8"),
            sa.Column("read_only", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not insp.has_table("ingest_raw"):
        op.create_table(
            "ingest_raw",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("profile_type", sa.String(32), nullable=False),
            sa.Column("source_table", sa.String(128), nullable=False),
            sa.Column("source_id", sa.String(64), nullable=False),
            sa.Column("entity_key", JSONB, nullable=False, server_default="{}"),
            sa.Column("raw_payload", JSONB, nullable=False),
            sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("batch_id", sa.Integer, nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["collection_tasks.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_ingest_raw_profile_type", "ingest_raw", ["profile_type"])
        op.create_index("ix_ingest_raw_source_table", "ingest_raw", ["source_table"])
        op.create_index("ix_ingest_raw_batch_id", "ingest_raw", ["batch_id"])

    if not insp.has_table("relation_staging"):
        op.create_table(
            "relation_staging",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("batch_id", sa.Integer, nullable=False),
            sa.Column("subject_name", sa.String(512), nullable=False),
            sa.Column("subject_type", sa.String(16), nullable=False),
            sa.Column("object_name", sa.String(512), nullable=False),
            sa.Column("object_type", sa.String(16), nullable=False),
            sa.Column("relation", sa.String(64), nullable=False),
            sa.Column("evidence", sa.Text),
            sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
            sa.Column("written", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["collection_tasks.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_relation_staging_batch_id", "relation_staging", ["batch_id"])

    if not insp.has_table("ingest_errors"):
        op.create_table(
            "ingest_errors",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("batch_id", sa.Integer, nullable=False),
            sa.Column("source_table", sa.String(128)),
            sa.Column("source_id", sa.String(64)),
            sa.Column("stage", sa.String(32), nullable=False),
            sa.Column("error_msg", sa.Text, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["collection_tasks.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_ingest_errors_batch_id", "ingest_errors", ["batch_id"])

    # profile 主表加质量评分列（幂等）
    for tbl in ("tech_profile", "org_profile", "person_profile", "project_profile"):
        cols = {c["name"] for c in insp.get_columns(tbl)}
        if "veracity_score" not in cols:
            op.add_column(tbl, sa.Column("veracity_score", sa.Float, nullable=False, server_default="0"))
        if "timeliness_score" not in cols:
            op.add_column(tbl, sa.Column("timeliness_score", sa.Float, nullable=False, server_default="0"))
        if "data_as_of" not in cols:
            op.add_column(tbl, sa.Column("data_as_of", sa.Date, nullable=True))


def downgrade() -> None:
    for tbl in ("tech_profile", "org_profile", "person_profile", "project_profile"):
        op.drop_column(tbl, "data_as_of")
        op.drop_column(tbl, "timeliness_score")
        op.drop_column(tbl, "veracity_score")
    op.drop_table("ingest_errors")
    op.drop_table("relation_staging")
    op.drop_table("ingest_raw")
    op.drop_table("db_connections")
