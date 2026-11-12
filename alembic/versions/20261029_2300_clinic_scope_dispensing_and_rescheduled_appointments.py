"""scope clinic data, track prescription pickup, and support rescheduled appointments

Revision ID: 20261029_2300
Revises: d82a6c1f0b37
Create Date: 2026-10-29 23:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261029_2300"
down_revision: Union[str, None] = "d82a6c1f0b37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prescriptions",
        sa.Column("picked_up", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "prescriptions",
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "prescriptions",
        sa.Column("picked_up_by_user_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_prescriptions_picked_up_by_user_id_users",
        "prescriptions",
        "users",
        ["picked_up_by_user_id"],
        ["id"],
    )
    op.alter_column("prescriptions", "picked_up", server_default=None)

    op.drop_index(
        "uq_appointments_staff_scheduled_at_active",
        table_name="appointments",
    )
    op.create_index(
        "uq_appointments_staff_scheduled_at_active",
        "appointments",
        ["staff_id", "scheduled_at"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('scheduled', 'rescheduled') AND deleted_at IS NULL"
        ),
        sqlite_where=sa.text(
            "status IN ('scheduled', 'rescheduled') AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_appointments_staff_scheduled_at_active",
        table_name="appointments",
    )
    op.create_index(
        "uq_appointments_staff_scheduled_at_active",
        "appointments",
        ["staff_id", "scheduled_at"],
        unique=True,
        postgresql_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
        sqlite_where=sa.text("status = 'scheduled' AND deleted_at IS NULL"),
    )
    op.drop_constraint(
        "fk_prescriptions_picked_up_by_user_id_users",
        "prescriptions",
        type_="foreignkey",
    )
    op.drop_column("prescriptions", "picked_up_by_user_id")
    op.drop_column("prescriptions", "picked_up_at")
    op.drop_column("prescriptions", "picked_up")
