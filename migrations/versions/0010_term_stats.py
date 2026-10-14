"""term_stats 表 — 术语窗口计数持久化(弱信号 Phase A3)

Revision ID: 0010_term_stats
Revises: 0009_llm_call_log
Create Date: 2026-10-14

修 spec 2026-10-14 §4.2 G7(无时序存储,每次全窗口重算):提取器每轮把
当前期各窗的 term df/tf upsert 进本表,后续新兴指标层(Phase B)直接读表。
ORM 见 metaprofile/new_tech_discovery/domain/orm_models.py:TermStatORM。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_term_stats"
down_revision: str | None = "0009_llm_call_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "term_stats"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("window_month", sa.Date(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="*"),
        sa.Column("term", sa.String(255), nullable=False),
        sa.Column("term_kind", sa.String(16), nullable=False, server_default="term"),
        sa.Column("df", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tf", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "window_month", "source", "term", "term_kind", name="uq_term_stats",
        ),
    )
    op.create_index(f"ix_{_TABLE}_window_month", _TABLE, ["window_month"])
    op.create_index(f"ix_{_TABLE}_term", _TABLE, ["term"])


def downgrade() -> None:
    op.drop_index(f"ix_{_TABLE}_term", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_window_month", table_name=_TABLE)
    op.drop_table(_TABLE)
