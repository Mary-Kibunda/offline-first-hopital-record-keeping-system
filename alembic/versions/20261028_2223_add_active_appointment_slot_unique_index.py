"""prevent active appointments from sharing a staff time slot

Revision ID: d82a6c1f0b37
Revises: 3be0014da301
Create Date: 2026-10-28 22:23:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d82a6c1f0b37"
down_revision: Union[str, None] = "3be0014da301"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_appointments_staff_scheduled_at_active",
        "appointments",
        ["staff_id", "scheduled_at"],
        unique=True,
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
        sqlite_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_appointments_staff_scheduled_at_active", table_name="appointments")
