"""新增配置表：llm_provider_configs / data_source_configs / collection_tasks

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_provider_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("api_key", sa.Text, nullable=True),
        sa.Column("api_base", sa.Text, nullable=True),
        sa.Column("model_role", sa.String(32), nullable=False, server_default="general"),
        sa.Column("max_tokens", sa.Integer, nullable=False, server_default="4096"),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.1"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("litellm_synced", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "data_source_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("profile_type", sa.String(32), nullable=False),
        sa.Column("config_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("schedule_cron", sa.String(64), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "collection_tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer, nullable=False),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("profile_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_imported", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("log_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["data_source_configs.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_collection_tasks_source_id", "collection_tasks", ["source_id"])
    op.create_index("ix_collection_tasks_status", "collection_tasks", ["status"])


def downgrade() -> None:
    op.drop_table("collection_tasks")
    op.drop_table("data_source_configs")
    op.drop_table("llm_provider_configs")
