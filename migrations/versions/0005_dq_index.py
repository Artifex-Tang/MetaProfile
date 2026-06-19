"""profile 4 表加 dq_index 列（数据质量复合评分）

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("tech_profile", "org_profile", "person_profile", "project_profile")


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)
    for tbl in _TABLES:
        cols = {c["name"] for c in insp.get_columns(tbl)}
        if "dq_index" not in cols:
            op.add_column(tbl, sa.Column("dq_index", sa.Float(), nullable=False, server_default="0.0"))


def downgrade() -> None:
    for tbl in _TABLES:
        op.drop_column(tbl, "dq_index")
