"""add shared login rate limits

Revision ID: 91d5f3a7c2e6
Revises: 4f2c8a9d1b73
Create Date: 2026-10-31 17:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91d5f3a7c2e6"
down_revision: Union[str, None] = "4f2c8a9d1b73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_rate_limits",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempts > 0", name="ck_login_rate_limits_attempts"),
        sa.PrimaryKeyConstraint("key_hash"),
    )
    op.create_index(
        "ix_login_rate_limits_window_started_at",
        "login_rate_limits",
        ["window_started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_login_rate_limits_window_started_at",
        table_name="login_rate_limits",
    )
    op.drop_table("login_rate_limits")
