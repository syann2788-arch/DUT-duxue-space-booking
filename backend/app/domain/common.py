"""Shared reservation constants, time helpers, and outbox writes."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, NotificationType, Reservation, ReservationStatus, local_now


OCCUPYING_STATUSES = (
    ReservationStatus.pending,
    ReservationStatus.approved,
    ReservationStatus.in_use,
    ReservationStatus.cleanup_pending,
    ReservationStatus.cleanup_rejected,
    ReservationStatus.active,
    ReservationStatus.checked_in,
)
DAILY_LIMIT_STATUSES = OCCUPYING_STATUSES


def slot_datetime(day: date, slot: int, config: dict) -> datetime:
    return datetime.combine(day, time(config["open_hour"], 0)) + timedelta(
        minutes=slot * config["slot_minutes"]
    )


def minute_datetime(day: date, minute: int) -> datetime:
    return datetime.combine(day, time.min) + timedelta(minutes=minute)


def reservation_start(reservation: Reservation, config: dict) -> datetime:
    minute = reservation.start_minute
    if minute is None:
        minute = config["open_hour"] * 60 + (reservation.start_slot or 0) * config["slot_minutes"]
    return minute_datetime(reservation.date, minute)


def reservation_end(reservation: Reservation, config: dict) -> datetime:
    minute = reservation.end_minute
    if minute is None:
        minute = config["open_hour"] * 60 + (reservation.end_slot or 0) * config["slot_minutes"]
    return minute_datetime(reservation.date, minute)


def slot_label(slot: int, config: dict) -> str:
    return slot_datetime(date.today(), slot, config).strftime("%H:%M")


def queue_notification(
    db: AsyncSession,
    user_id: int,
    reservation_id: int | None,
    kind: NotificationType,
    payload: dict,
    scheduled_at: datetime | None = None,
) -> None:
    db.add(Notification(
        user_id=user_id,
        reservation_id=reservation_id,
        type=kind,
        payload=payload,
        scheduled_at=scheduled_at or local_now(),
    ))
