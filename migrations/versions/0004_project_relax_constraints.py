"""project_profile: 放松 project_no UNIQUE + start_date nullable (ODS 批量灌库需要)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)

    # drop unique constraint on project_no (name varies by backend; drop via introspection)
    for uq in insp.get_unique_constraints("project_profile"):
        if "project_no" in uq.get("column_names", []):
            op.drop_constraint(uq["name"], "project_profile", type_="unique")
    for ix in insp.get_indexes("project_profile"):
        if "project_no" in ix.get("column_names", []) and ix.get("unique"):
            op.drop_index(ix["name"], table_name="project_profile")

    # start_date nullable
    cols = {c["name"]: c for c in insp.get_columns("project_profile")}
    if "start_date" in cols and not cols["start_date"].get("nullable", True):
        op.alter_column(
            "project_profile",
            "start_date",
            existing_type=sa.Date(),
            nullable=True,
        )


def downgrade() -> None:
    op.alter_column(
        "project_profile",
        "start_date",
        existing_type=sa.Date(),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_project_profile_project_no", "project_profile", ["project_no"]
    )
