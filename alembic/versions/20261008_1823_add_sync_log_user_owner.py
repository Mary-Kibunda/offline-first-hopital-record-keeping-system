"""associate sync history with the authenticated user

Revision ID: 8f7c4b2d1a60
Revises: 2b9e7f2527e1
Create Date: 2026-10-08 18:23:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f7c4b2d1a60"
down_revision: Union[str, None] = "2b9e7f2527e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sync_log", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_sync_log_user_id_users",
        "sync_log",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_index("ix_sync_log_user_id", "sync_log", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sync_log_user_id", table_name="sync_log")
    op.drop_constraint("fk_sync_log_user_id_users", "sync_log", type_="foreignkey")
    op.drop_column("sync_log", "user_id")
