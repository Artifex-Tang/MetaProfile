"""tech_emergence_indicator 表 — 新兴指标持久化(Phase B)

Revision ID: 0011_emergence_indicator
Revises: 0010_term_stats
Create Date: 2026-10-14

对象(IPC 域/IPC 对)× 窗口(年)× 指标 JSONB(Porter/TLC/TEM/Salton)。
ORM 见 metaprofile/new_tech_discovery/domain/orm_models.py:TechEmergenceIndicatorORM。
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_emergence_indicator"
down_revision: Union[str, None] = "0010_term_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "tech_emergence_indicator"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("object_type", sa.String(16), nullable=False),
        sa.Column("object_id", sa.String(128), nullable=False),
        sa.Column("window_month", sa.Date(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "object_type", "object_id", "window_month",
            name="uq_emergence_object_window",
        ),
    )
    op.create_index(f"ix_{_TABLE}_object_type", _TABLE, ["object_type"])
    op.create_index(f"ix_{_TABLE}_object_id", _TABLE, ["object_id"])
    op.create_index(f"ix_{_TABLE}_window_month", _TABLE, ["window_month"])


def downgrade() -> None:
    op.drop_index(f"ix_{_TABLE}_window_month", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_object_id", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_object_type", table_name=_TABLE)
    op.drop_table(_TABLE)
