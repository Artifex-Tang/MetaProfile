"""tech_profile 分层列 + tech_evidence 证据表（技术概念抽取 P1）

Revision ID: 0008_tech_concept
Revises: 0007
Create Date: 2026-06-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_tech_concept"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROFILE = "tech_profile"
_EVIDENCE = "tech_evidence"


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)

    # 1) tech_profile 加 4 个分层列（幂等：列存在则跳过）
    existing_cols = {c["name"] for c in insp.get_columns(_PROFILE)}
    if "tech_layer" not in existing_cols:
        op.add_column(
            _PROFILE,
            sa.Column("tech_layer", sa.String(length=16), nullable=False, server_default="CONCEPT"),
        )
    if "ipc_code" not in existing_cols:
        op.add_column(_PROFILE, sa.Column("ipc_code", sa.String(length=32), nullable=True))
    if "parent_ipc_code" not in existing_cols:
        op.add_column(_PROFILE, sa.Column("parent_ipc_code", sa.String(length=32), nullable=True))
    if "cluster_terms" not in existing_cols:
        op.add_column(
            _PROFILE,
            sa.Column("cluster_terms", sa.JSON(), nullable=False, server_default="[]"),
        )

    # 2) tech_evidence 证据表（幂等：表存在则跳过）
    if _EVIDENCE not in insp.get_table_names():
        op.create_table(
            _EVIDENCE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "tech_id",
                sa.String(length=64),
                sa.ForeignKey("tech_profile.tech_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("source_doc_id", sa.String(length=128), nullable=False),
            sa.Column("source_table", sa.String(length=128), nullable=False),
            sa.Column("snippet", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("tech_id", "source_doc_id", "source_table", name="uq_tech_evidence"),
        )
        op.create_index("ix_tech_evidence_tech_id", _EVIDENCE, ["tech_id"])


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)

    if _EVIDENCE in insp.get_table_names():
        op.drop_index("ix_tech_evidence_tech_id", table_name=_EVIDENCE)
        op.drop_table(_EVIDENCE)

    existing_cols = {c["name"] for c in insp.get_columns(_PROFILE)}
    for col in ("cluster_terms", "parent_ipc_code", "ipc_code", "tech_layer"):
        if col in existing_cols:
            op.drop_column(_PROFILE, col)
