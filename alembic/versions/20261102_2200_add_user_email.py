"""add email to users (welcome email and password reset)

Revision ID: 20261102_2200
Revises: 20261029_2300
Create Date: 2026-11-02 22:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261102_2200"
down_revision: Union[str, None] = "20261029_2300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing accounts have no email yet. Postgres allows many NULLs
    # in a unique index, so the unique constraint only bites on real addresses.
    op.add_column("users", sa.Column("email", sa.String(length=254), nullable=True))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "email")
