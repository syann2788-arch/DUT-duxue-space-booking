"""Async database setup and a small v1-to-v2 compatibility bridge.

Production deployments should use PostgreSQL and Alembic-style migrations.  The
compatibility bridge only exists so the historical SQLite demo can be opened
without deleting user data.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            await _upgrade_legacy_sqlite(conn)


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

    result = await conn.execute(text("PRAGMA table_info(rooms)"))
    room_columns = {row[1] for row in result.fetchall()}
    if room_columns and "capacity" not in room_columns:
        await conn.execute(text("ALTER TABLE rooms ADD COLUMN capacity INTEGER NOT NULL DEFAULT 1"))

    result = await conn.execute(text("PRAGMA table_info(users)"))
    user_columns = {row[1] for row in result.fetchall()}
    if user_columns and "wechat_openid" not in user_columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN wechat_openid VARCHAR(64)"))
