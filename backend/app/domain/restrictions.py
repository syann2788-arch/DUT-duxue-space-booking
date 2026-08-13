"""Booking restrictions and violation threshold ownership."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common import queue_notification
from app.models import (
    BookingRestriction, Notification, NotificationStatus, NotificationType,
    RestrictionLevel, User, Violation, ViolationType, local_now,
)
from app.schemas import RestrictionCreate


async def active_restriction(db: AsyncSession, user: User, now: datetime) -> BookingRestriction | None:
    if user.banned_until and user.banned_until > now:
        return BookingRestriction(user_id=user.id, level=RestrictionLevel.timed, reason="历史封禁", ends_at=user.banned_until)
    result = await db.execute(select(BookingRestriction).where(
        BookingRestriction.user_id == user.id,
        BookingRestriction.is_active.is_(True),
    ).order_by(BookingRestriction.created_at.desc()))
    for restriction in result.scalars():
        if restriction.ends_at and restriction.ends_at <= now:
            restriction.is_active = False
            restriction.revoked_at = now
            continue
        return restriction
    await db.flush()
    return None


async def get_active_restriction(db: AsyncSession, user: User, now: datetime | None = None) -> BookingRestriction | None:
    return await active_restriction(db, user, now or local_now())


async def expire_restrictions(db: AsyncSession, now: datetime | None = None) -> int:
    now = now or local_now()
    result = await db.execute(select(BookingRestriction).where(
        BookingRestriction.is_active.is_(True),
        BookingRestriction.ends_at.is_not(None),
        BookingRestriction.ends_at <= now,
    ).with_for_update())
    restrictions = list(result.scalars())
    for restriction in restrictions:
        restriction.is_active = False
        restriction.revoked_at = now
    if restrictions:
        await db.commit()
    return len(restrictions)


async def add_restriction(db: AsyncSession, user_id: int, data: RestrictionCreate, admin_id: int | None, commit: bool = True) -> BookingRestriction:
    if not await db.get(User, user_id):
        raise HTTPException(404, "用户不存在")
    now = local_now()
    ends_at = None if data.level == RestrictionLevel.permanent else now + timedelta(days=data.days or 1)
    restriction = BookingRestriction(user_id=user_id, level=data.level, reason=data.reason, ends_at=ends_at, created_by=admin_id)
    db.add(restriction)
    await db.flush()
    queue_notification(db, user_id, None, NotificationType.restriction, {
        "change": "restricted", "restriction_id": restriction.id, "level": data.level.value,
        "reason": data.reason, "ends_at": ends_at.isoformat() if ends_at else "永久",
    })
    if ends_at:
        queue_notification(db, user_id, None, NotificationType.restriction, {
            "change": "expired", "restriction_id": restriction.id, "level": data.level.value,
            "reason": "预约限制已到期，预约权限已自动恢复", "ends_at": ends_at.isoformat(),
        }, scheduled_at=ends_at)
    if commit:
        await db.commit()
        await db.refresh(restriction)
    else:
        await db.flush()
    return restriction


async def revoke_restriction(db: AsyncSession, restriction_id: int) -> bool:
    restriction = await db.get(BookingRestriction, restriction_id)
    if not restriction:
        return False
    restriction.is_active = False
    restriction.revoked_at = local_now()
    pending = list((await db.scalars(select(Notification).where(
        Notification.user_id == restriction.user_id,
        Notification.type == NotificationType.restriction,
        Notification.status == NotificationStatus.pending,
    ))).all())
    for notification in pending:
        if notification.payload.get("change") == "expired" and notification.payload.get("restriction_id") == restriction.id:
            await db.delete(notification)
    queue_notification(db, restriction.user_id, None, NotificationType.restriction, {
        "change": "revoked", "level": "revoked", "reason": "管理员已解除预约限制",
        "ends_at": local_now().isoformat(),
    })
    await db.commit()
    return True


async def record_violation(
    db: AsyncSession,
    user_id: int,
    reservation_id: int,
    violation_type: ViolationType,
    now: datetime,
    config: dict,
) -> bool:
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    existing = await db.scalar(select(Violation.id).where(
        Violation.reservation_id == reservation_id,
        Violation.type == violation_type,
    ))
    if existing:
        return False
    db.add(Violation(user_id=user_id, reservation_id=reservation_id, type=violation_type, created_at=now))
    await db.flush()
    count = int(await db.scalar(select(func.count(Violation.id)).where(Violation.user_id == user_id)) or 0)
    threshold = int(config["violation_threshold"])
    if count % threshold == 0:
        days = int(config["violation_ban_days"])
        await add_restriction(
            db, user_id,
            RestrictionCreate(level=RestrictionLevel.timed, days=days, reason=f"累计{count}次违约，自动禁约{days}天"),
            admin_id=None, commit=False,
        )
    return True
