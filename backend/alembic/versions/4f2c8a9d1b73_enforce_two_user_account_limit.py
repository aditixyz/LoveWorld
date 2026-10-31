"""enforce the two-user account limit

Revision ID: 4f2c8a9d1b73
Revises: ff850c33e28e
Create Date: 2026-10-31 16:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f2c8a9d1b73"
down_revision: Union[str, None] = "ff850c33e28e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_slot", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE users AS target_user
        SET account_slot = (
            SELECT COUNT(*)
            FROM users AS prior_user
            WHERE prior_user.id <= target_user.id
        )
        """
    )

    op.alter_column(
        "users",
        "account_slot",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_users_account_slot",
        "users",
        "account_slot IN (1, 2)",
    )
    op.create_unique_constraint(
        "uq_users_account_slot",
        "users",
        ["account_slot"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_account_slot", "users", type_="unique")
    op.drop_constraint("ck_users_account_slot", "users", type_="check")
    op.drop_column("users", "account_slot")
