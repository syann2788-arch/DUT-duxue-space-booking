"""Async database setup and a small v1-to-v2 compatibility bridge.

Production deployments should use PostgreSQL and Alembic-style migrations.  The
compatibility bridge only exists so the historical SQLite demo can be opened
without deleting user data.
"""
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


SCHEMA_REVISION = "20260813_01"


engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    # Import models before create_all so metadata is populated.
    from app import models  # noqa: F401

    if settings.is_production:
        current = await current_schema_revision()
        if current != SCHEMA_REVISION:
            raise RuntimeError(
                f"数据库版本不匹配：当前 {current or '未迁移'}，要求 {SCHEMA_REVISION}；"
                "请先执行 alembic upgrade head"
            )
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            logging.getLogger("duxue").warning(
                '{"event":"sqlite_development_only","message":"SQLite 不支持生产行锁，仅限本地开发"}'
            )
            await _upgrade_legacy_sqlite(conn)


async def current_schema_revision() -> str | None:
    try:
        async with engine.connect() as conn:
            return await conn.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError:
        return None


async def database_ready() -> tuple[bool, str | None]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, None
    except SQLAlchemyError as exc:
        return False, exc.__class__.__name__


async def _upgrade_legacy_sqlite(conn) -> None:
    """Add non-destructive v2 columns to a v1 SQLite database."""
    result = await conn.execute(text("PRAGMA table_info(reservations)"))
    columns = {row[1] for row in result.fetchall()}
    additions = {
        "start_slot": "INTEGER",
        "end_slot": "INTEGER",
        "start_minute": "INTEGER",
        "end_minute": "INTEGER",
        "scene": "VARCHAR(20)",
        "usage_mode": "VARCHAR(20)",
        "people_count": "INTEGER NOT NULL DEFAULT 1",
        "purpose": "VARCHAR(300) NOT NULL DEFAULT ''",
        "campus_card_photo_url": "VARCHAR(500)",
        "campus_card_media_id": "VARCHAR(36)",
        "review_note": "VARCHAR(500)",
        "reviewed_by": "INTEGER",
        "reviewed_at": "DATETIME",
        "auto_approved": "BOOLEAN NOT NULL DEFAULT 0",
    }
    for name, ddl in additions.items():
        if name not in columns:
            await conn.execute(text(f"ALTER TABLE reservations ADD COLUMN {name} {ddl}"))
    if columns:
        await conn.execute(text(
            "UPDATE reservations SET start_slot=(start_hour-8)*2, end_slot=(end_hour-8)*2 "
            "WHERE start_slot IS NULL AND start_hour IS NOT NULL"
        ))
        await conn.execute(text(
            "UPDATE reservations SET start_minute=COALESCE(start_hour*60, 480+start_slot*30), "
            "end_minute=COALESCE(end_hour*60, 480+end_slot*30) WHERE start_minute IS NULL"
        ))
        # V1 had no shared/exclusive field and treated every room booking as a
        # whole-room conflict. Preserve that safer meaning during migration.
        await conn.execute(text(
            "UPDATE reservations SET usage_mode='exclusive' WHERE usage_mode IS NULL"
        ))

    result = await conn.execute(text("PRAGMA table_info(rooms)"))
    room_columns = {row[1] for row in result.fetchall()}
    if room_columns and "capacity" not in room_columns:
        await conn.execute(text("ALTER TABLE rooms ADD COLUMN capacity INTEGER NOT NULL DEFAULT 1"))

    result = await conn.execute(text("PRAGMA table_info(users)"))
    user_columns = {row[1] for row in result.fetchall()}
    if user_columns and "wechat_openid" not in user_columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN wechat_openid VARCHAR(64)"))

    result = await conn.execute(text("PRAGMA table_info(cleanup_verifications)"))
    cleanup_columns = {row[1] for row in result.fetchall()}
    if cleanup_columns and "media_ids" not in cleanup_columns:
        await conn.execute(text("ALTER TABLE cleanup_verifications ADD COLUMN media_ids JSON NOT NULL DEFAULT '[]'"))

    result = await conn.execute(text("PRAGMA table_info(private_media)"))
    media_columns = {row[1] for row in result.fetchall()}
    if media_columns and "deleted_at" not in media_columns:
        await conn.execute(text("ALTER TABLE private_media ADD COLUMN deleted_at DATETIME"))

    # Existing SQLite databases predate the ORM uniqueness rule.
    await conn.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_violation_reservation_type "
        "ON violations (reservation_id, type)"
    ))
