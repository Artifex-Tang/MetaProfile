"""entity_resolution_suggestion 表 — 实体归一/消歧/分类建议(Phase D)

Revision ID: 0013_entity_resolution
Revises: 0012_disruption_assessment
Create Date: 2026-10-14

只产建议不自动合并(spec 2026-10-14 §6-D):
- org: ROR API/别名字典匹配建议(ror_match)
- person: 作者消歧规则聚类建议(author_dedup)
- project: LLM 零样本 IPC 域分类(project_classify)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_entity_resolution"
down_revision: Union[str, None] = "0012_disruption_assessment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "entity_resolution_suggestion"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(16), nullable=False),   # org|person|project
        sa.Column("raw_name", sa.String(512), nullable=False),
        sa.Column("suggestion_kind", sa.String(32), nullable=False),  # ror_match|author_dedup|project_classify
        sa.Column("matched_id", sa.String(128)),
        sa.Column("matched_name", sa.String(512)),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("detail", sa.JSON()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),  # pending|applied|rejected
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "entity_type", "raw_name", "suggestion_kind",
            name="uq_ers_entity_kind_name",
        ),
    )
    op.create_index(f"ix_{_TABLE}_entity_type", _TABLE, ["entity_type"])
    op.create_index(f"ix_{_TABLE}_status", _TABLE, ["status"])


def downgrade() -> None:
    op.drop_index(f"ix_{_TABLE}_status", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_entity_type", table_name=_TABLE)
    op.drop_table(_TABLE)
