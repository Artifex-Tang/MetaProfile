"""llm_call_log 表 — LLM 调用 token/cost/latency 计量

Revision ID: 0009_llm_call_log
Revises: 0008_tech_concept
Create Date: 2026-06-24

消除 gateway.py record_call_async 每次调用的 llm_call_log_record_failed 噪声
(表缺失 → 每次 LLM 调用记一条 warning),并启用 token/cost/latency 审计。
ORM 见 metaprofile/shared/llm/token_meter.py:LLMCallLog。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_llm_call_log"
down_revision: Union[str, None] = "0008_tech_concept"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "llm_call_log"


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)

    # 幂等:表存在则跳过
    if _TABLE in insp.get_table_names():
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("caller", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cost_cny",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_llm_call_log_called_at", _TABLE, ["called_at"])
    op.create_index("ix_llm_call_log_caller", _TABLE, ["caller"])
    op.create_index("ix_llm_call_log_model", _TABLE, ["model"])


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)

    if _TABLE in insp.get_table_names():
        op.drop_index("ix_llm_call_log_model", table_name=_TABLE)
        op.drop_index("ix_llm_call_log_caller", table_name=_TABLE)
        op.drop_index("ix_llm_call_log_called_at", table_name=_TABLE)
        op.drop_table(_TABLE)
