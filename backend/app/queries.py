"""Bounded read models shared by the API and export workflows."""
from __future__ import annotations

from datetime import date
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import (
    CleanupStatus,
    CleanupVerification,
    Reservation,
    ReservationStatus,
    Room,
    SceneType,
    User,
)
from app.domain.reservations import refresh_reservation_states


def _page(query, *, limit: int | None, offset: int):
    return query if limit is None else query.limit(limit).offset(offset)


async def get_user_reservations(
    db: AsyncSession,
    user_id: int,
    status_filters: Sequence[ReservationStatus] | None = None,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[Reservation], int]:
    await refresh_reservation_states(db)
    query = select(Reservation).options(
        joinedload(Reservation.room).selectinload(Room.scene_rules),
        joinedload(Reservation.user),
        joinedload(Reservation.cleanup),
    ).where(Reservation.user_id == user_id)
    if status_filters:
        query = query.where(Reservation.status.in_(status_filters))
    total = int(await db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    ordered = query.order_by(Reservation.date.desc(), Reservation.start_slot.desc(), Reservation.id.desc())
    result = await db.execute(_page(ordered, limit=limit, offset=offset))
    return list(result.scalars().unique()), total


async def list_admin_reservations(
    db: AsyncSession,
    day: date | None = None,
    reservation_status: ReservationStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    scene: SceneType | None = None,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[Reservation], int]:
    await refresh_reservation_states(db)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "开始日期不能晚于结束日期")
    query = select(Reservation).options(
        joinedload(Reservation.room).selectinload(Room.scene_rules),
        joinedload(Reservation.user),
        joinedload(Reservation.cleanup),
    )
    if day:
        query = query.where(Reservation.date == day)
    if reservation_status:
        query = query.where(Reservation.status == reservation_status)
    if date_from:
        query = query.where(Reservation.date >= date_from)
    if date_to:
        query = query.where(Reservation.date <= date_to)
    if scene:
        query = query.where(Reservation.scene == scene)
    total = int(await db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    ordered = query.order_by(Reservation.created_at.desc(), Reservation.id.desc())
    result = await db.execute(_page(ordered, limit=limit, offset=offset))
    return list(result.scalars().unique()), total


async def list_cleanup_queue(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Reservation], int]:
    base = select(Reservation).join(CleanupVerification).where(
        CleanupVerification.status == CleanupStatus.pending
    )
    total = int(await db.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0)
    query = base.options(
        joinedload(Reservation.room).selectinload(Room.scene_rules),
        joinedload(Reservation.user),
        joinedload(Reservation.cleanup),
    ).order_by(CleanupVerification.submitted_at, Reservation.id)
    result = await db.execute(query.limit(limit).offset(offset))
    return list(result.scalars().unique()), total


async def get_all_users(
    db: AsyncSession,
    search: str | None = None,
    *,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[User], int]:
    query = select(User)
    if search and search.strip():
        keyword = f"%{search.strip()}%"
        query = query.where(or_(
            User.student_id.ilike(keyword),
            User.name.ilike(keyword),
            User.phone.ilike(keyword),
            User.class_name.ilike(keyword),
        ))
    total = int(await db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    users = list((await db.scalars(query.order_by(User.student_id).limit(limit).offset(offset))).all())
    return users, total
