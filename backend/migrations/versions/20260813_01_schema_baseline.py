"""Current v2 schema baseline.

Revision ID: 20260813_01
Revises: None
"""
from alembic import op
import sqlalchemy as sa

from app.database import Base
from app import models  # noqa: F401


revision = "20260813_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    inspector = sa.inspect(bind)
    additions = {
        "reservations": {
            "start_slot": sa.Column("start_slot", sa.Integer(), nullable=True),
            "end_slot": sa.Column("end_slot", sa.Integer(), nullable=True),
            "start_minute": sa.Column("start_minute", sa.Integer(), nullable=True),
            "end_minute": sa.Column("end_minute", sa.Integer(), nullable=True),
            "scene": sa.Column("scene", sa.String(20), nullable=True),
            "usage_mode": sa.Column("usage_mode", sa.String(20), nullable=True),
            "people_count": sa.Column("people_count", sa.Integer(), nullable=False, server_default="1"),
            "purpose": sa.Column("purpose", sa.String(300), nullable=False, server_default=""),
            "campus_card_photo_url": sa.Column("campus_card_photo_url", sa.String(500), nullable=True),
            "campus_card_media_id": sa.Column("campus_card_media_id", sa.String(36), nullable=True),
            "review_note": sa.Column("review_note", sa.String(500), nullable=True),
            "reviewed_by": sa.Column("reviewed_by", sa.Integer(), nullable=True),
            "reviewed_at": sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            "auto_approved": sa.Column("auto_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        },
        "rooms": {
            "capacity": sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        },
        "users": {
            "wechat_openid": sa.Column("wechat_openid", sa.String(64), nullable=True),
        },
        "cleanup_verifications": {
            "media_ids": sa.Column("media_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        },
        "private_media": {
            "deleted_at": sa.Column("deleted_at", sa.DateTime(), nullable=True),
        },
    }
    for table_name, columns in additions.items():
        if not inspector.has_table(table_name):
            continue
        existing = {item["name"] for item in inspector.get_columns(table_name)}
        for column_name, column in columns.items():
            if column_name not in existing:
                op.add_column(table_name, column)
    if inspector.has_table("reservations"):
        op.execute(
            "UPDATE reservations SET start_slot=(start_hour-8)*2, end_slot=(end_hour-8)*2 "
            "WHERE start_slot IS NULL AND start_hour IS NOT NULL"
        )
        op.execute(
            "UPDATE reservations SET start_minute=COALESCE(start_hour*60, 480+start_slot*30), "
            "end_minute=COALESCE(end_hour*60, 480+end_slot*30) WHERE start_minute IS NULL"
        )
        op.execute("UPDATE reservations SET usage_mode='exclusive' WHERE usage_mode IS NULL")
        indexes = {item["name"] for item in inspector.get_indexes("reservations")}
        if "ix_reservations_campus_card_media_id" not in indexes:
            op.create_index("ix_reservations_campus_card_media_id", "reservations", ["campus_card_media_id"])
    if inspector.has_table("private_media"):
        indexes = {item["name"] for item in inspector.get_indexes("private_media")}
        if "ix_private_media_deleted_at" not in indexes:
            op.create_index("ix_private_media_deleted_at", "private_media", ["deleted_at"])
    if inspector.has_table("violations"):
        uniques = {item["name"] for item in inspector.get_unique_constraints("violations")}
        indexes = {item["name"] for item in inspector.get_indexes("violations")}
        if "uq_violation_reservation_type" not in uniques | indexes:
            op.create_index(
                "uq_violation_reservation_type", "violations", ["reservation_id", "type"], unique=True
            )


def downgrade() -> None:
    raise RuntimeError("基线迁移不可破坏性降级；请按运行手册恢复发布前备份")
