"""disruption_assessment 表 — 颠覆性评估持久化(Phase C)

Revision ID: 0012_disruption_assessment
Revises: 0011_emergence_indicator
Create Date: 2026-10-14

组合新颖/增速/新进入者/小团队/术语新度 z 分 + DisruptScore + LLM Rotolo rubric。
ORM 见 metaprofile/new_tech_discovery/domain/orm_models.py:DisruptionAssessmentORM。
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_disruption_assessment"
down_revision: Union[str, None] = "0011_emergence_indicator"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "disruption_assessment"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("object_type", sa.String(16), nullable=False),
        sa.Column("object_id", sa.String(128), nullable=False),
        sa.Column("window_month", sa.Date(), nullable=False),
        sa.Column("novelty_comb", sa.Float(), nullable=False, server_default="0"),
        sa.Column("growth", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_entrant", sa.Float(), nullable=False, server_default="0"),
        sa.Column("small_team", sa.Float(), nullable=False, server_default="0"),
        sa.Column("term_novelty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("disrupt_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("llm_verdict", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("llm_scores", sa.JSON()),
        sa.Column("llm_evidence", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "object_type", "object_id", "window_month",
            name="uq_disruption_object_window",
        ),
    )
    op.create_index(f"ix_{_TABLE}_object_type", _TABLE, ["object_type"])
    op.create_index(f"ix_{_TABLE}_object_id", _TABLE, ["object_id"])
    op.create_index(f"ix_{_TABLE}_window_month", _TABLE, ["window_month"])
    op.create_index(f"ix_{_TABLE}_disrupt_score", _TABLE, ["disrupt_score"])


def downgrade() -> None:
    for idx in ("disrupt_score", "window_month", "object_id", "object_type"):
        op.drop_index(f"ix_{_TABLE}_{idx}", table_name=_TABLE)
    op.drop_table(_TABLE)
