"""Add composite indexes for reservation state and history queries.

Revision ID: 20260813_02
Revises: 20260813_01
"""
from alembic import op
import sqlalchemy as sa


revision = "20260813_02"
down_revision = "20260813_01"
branch_labels = None
depends_on = None


INDEXES = {
    "ix_reservations_status_date": ["status", "date"],
    "ix_reservations_user_date": ["user_id", "date"],
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {item["name"] for item in inspector.get_indexes("reservations")}
    for name, columns in INDEXES.items():
        if name not in existing:
            op.create_index(name, "reservations", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {item["name"] for item in inspector.get_indexes("reservations")}
    for name in reversed(tuple(INDEXES)):
        if name in existing:
            op.drop_index(name, table_name="reservations")
