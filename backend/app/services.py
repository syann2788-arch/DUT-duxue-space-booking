"""Transactional business services.

Routers deliberately stay thin: every authorization-independent business rule is
implemented here so H5, WeChat and future administrative clients behave equally.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.config import DEFAULT_RUNTIME_CONFIG
from app.models import (
    BookingRestriction,
    CleanupStatus,
    CleanupVerification,
    Notification,
    NotificationStatus,
    NotificationType,
    PublicStatus,
    Reservation,
    ReservationStatus,
    RestrictionLevel,
    Room,
    RoomSceneRule,
    SceneType,
    SystemSetting,
    UsageMode,
    User,
    UserRole,
    local_now,
)
from app.schemas import CleanupReviewRequest, ReservationCreate, ReservationReviewRequest, RestrictionCreate


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


async def get_runtime_config(db: AsyncSession) -> dict:
    result = await db.execute(select(SystemSetting))
    values = dict(DEFAULT_RUNTIME_CONFIG)
    values.update({item.key: item.value for item in result.scalars() if item.key in DEFAULT_RUNTIME_CONFIG})
    return values


async def update_runtime_config(db: AsyncSession, values: dict, admin_id: int) -> dict:
    allowed = set(DEFAULT_RUNTIME_CONFIG)
    unknown = set(values) - allowed
    if unknown:
        raise HTTPException(400, f"未知配置项: {', '.join(sorted(unknown))}")
    merged = {**await get_runtime_config(db), **values}
    _validate_runtime_config(merged)
    for key, value in values.items():
        setting = await db.get(SystemSetting, key)
        if setting:
            setting.value = value
            setting.updated_by = admin_id
        else:
            db.add(SystemSetting(key=key, value=value, updated_by=admin_id))
    await db.commit()
    return await get_runtime_config(db)


def _validate_runtime_config(config: dict) -> None:
    if config["open_hour"] < 0 or config["close_hour"] > 24 or config["open_hour"] >= config["close_hour"]:
        raise HTTPException(400, "开放时段配置无效")
    if config["slot_minutes"] not in (15, 30, 60):
        raise HTTPException(400, "预约粒度只能为15、30或60分钟")
    if 60 % config["slot_minutes"]:
        raise HTTPException(400, "预约粒度必须整除60分钟")
    if config["max_minutes_per_day"] < config["slot_minutes"]:
        raise HTTPException(400, "单日时长上限不能小于一个时段")
    try:
        time.fromisoformat(config["auto_approval_time"])
    except (TypeError, ValueError):
        raise HTTPException(400, "自动审批时间应为 HH:MM")


def slot_datetime(day: date, slot: int, config: dict) -> datetime:
    return datetime.combine(day, time(config["open_hour"], 0)) + timedelta(minutes=slot * config["slot_minutes"])


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


async def get_user_by_student_id(db: AsyncSession, student_id: str) -> User | None:
    return (await db.execute(select(User).where(User.student_id == student_id))).scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def create_user(db: AsyncSession, student_id: str, name: str, phone: str, class_name: str, password_hash: str) -> User:
    user = User(student_id=student_id, name=name, phone=phone, class_name=class_name, password_hash=password_hash)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_active_rooms(db: AsyncSession) -> list[Room]:
    result = await db.execute(
        select(Room).options(selectinload(Room.scene_rules)).where(Room.is_active.is_(True)).order_by(Room.room_code)
    )
    return list(result.scalars().unique())


async def get_room_by_id(db: AsyncSession, room_id: int) -> Room | None:
    result = await db.execute(select(Room).options(selectinload(Room.scene_rules)).where(Room.id == room_id))
    return result.scalar_one_or_none()


async def update_public_status(db: AsyncSession, room_id: int, public_status: PublicStatus) -> Room | None:
    room = await db.get(Room, room_id)
    if not room or not room.is_public:
        return None
    room.public_status = public_status
    await db.commit()
    await db.refresh(room)
    return room


async def refresh_reservation_states(db: AsyncSession, now: datetime | None = None) -> None:
    """Advance time-derived states. Safe to run from requests and scheduler."""
    now = now or local_now()
    config = await get_runtime_config(db)
    result = await db.execute(select(Reservation).where(Reservation.status.in_(OCCUPYING_STATUSES)))
    changed = False
    for reservation in result.scalars():
        if reservation.start_slot is None or reservation.end_slot is None:
            continue
        start = reservation_start(reservation, config)
        end = reservation_end(reservation, config)
        if reservation.status in (ReservationStatus.approved, ReservationStatus.active) and now > start + timedelta(minutes=config["checkin_grace_minutes"]):
            reservation.status = ReservationStatus.missed
            changed = True
        elif reservation.status in (ReservationStatus.in_use, ReservationStatus.checked_in) and now >= end:
            reservation.status = ReservationStatus.cleanup_pending
            changed = True
    if changed:
        await db.commit()


async def _active_restriction(db: AsyncSession, user: User, now: datetime) -> BookingRestriction | None:
    if user.banned_until and user.banned_until > now:
        return BookingRestriction(user_id=user.id, level=RestrictionLevel.timed, reason="历史封禁", ends_at=user.banned_until)
    result = await db.execute(
        select(BookingRestriction).where(
            BookingRestriction.user_id == user.id,
            BookingRestriction.is_active.is_(True),
        ).order_by(BookingRestriction.created_at.desc())
    )
    for restriction in result.scalars():
        if restriction.ends_at and restriction.ends_at <= now:
            restriction.is_active = False
            restriction.revoked_at = now
            continue
        return restriction
    await db.flush()
    return None


async def _ensure_user_can_book(db: AsyncSession, user: User, now: datetime) -> None:
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    restriction = await _active_restriction(db, user, now)
    if restriction:
        until = restriction.ends_at.strftime("%Y-%m-%d %H:%M") if restriction.ends_at else "永久"
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"预约资格受限（{until}）：{restriction.reason}")
    unresolved = await db.scalar(select(func.count(Reservation.id)).where(
        Reservation.user_id == user.id,
        Reservation.status.in_((ReservationStatus.cleanup_pending, ReservationStatus.cleanup_rejected)),
    ))
    if unresolved:
        raise HTTPException(status.HTTP_409_CONFLICT, "请先上传并通过上一笔预约的现场清扫照片")


async def _daily_minutes(db: AsyncSession, user_id: int, day: date, config: dict) -> int:
    result = await db.execute(select(Reservation.start_minute, Reservation.end_minute, Reservation.start_slot, Reservation.end_slot).where(
        Reservation.user_id == user_id,
        Reservation.date == day,
        Reservation.status.in_(DAILY_LIMIT_STATUSES),
    ))
    total = 0
    for start_minute, end_minute, start_slot, end_slot in result:
        if start_minute is not None and end_minute is not None:
            total += end_minute - start_minute
        elif start_slot is not None and end_slot is not None:
            total += (end_slot - start_slot) * config["slot_minutes"]
    return total


async def _overlaps(db: AsyncSession, room_id: int, data: ReservationCreate, start_minute: int, end_minute: int) -> list[Reservation]:
    result = await db.execute(select(Reservation).where(
        Reservation.room_id == room_id,
        Reservation.date == data.date,
        Reservation.status.in_(OCCUPYING_STATUSES),
        Reservation.start_minute < end_minute,
        Reservation.end_minute > start_minute,
    ).with_for_update())
    return list(result.scalars())


async def _candidate_available(db: AsyncSession, rule: RoomSceneRule, data: ReservationCreate, start_minute: int, end_minute: int) -> bool:
    existing = await _overlaps(db, rule.room_id, data, start_minute, end_minute)
    if rule.usage_mode == UsageMode.exclusive:
        return not existing
    if any(item.usage_mode == UsageMode.exclusive for item in existing):
        return False
    return sum(item.people_count for item in existing) + data.people_count <= rule.capacity


async def _event_music_conflicts(db: AsyncSession, scene: SceneType, data: ReservationCreate, start_minute: int, end_minute: int) -> list[Reservation]:
    other_code = "B102" if scene == SceneType.event else "A103"
    result = await db.execute(select(Reservation).join(Room).where(
        Room.room_code == other_code,
        Reservation.date == data.date,
        Reservation.status.in_(OCCUPYING_STATUSES),
        Reservation.start_minute < end_minute,
        Reservation.end_minute > start_minute,
    ).with_for_update())
    return list(result.scalars())


async def create_reservation(db: AsyncSession, user_id: int, data: ReservationCreate) -> Reservation:
    now = local_now()
    await refresh_reservation_states(db, now)
    config = await get_runtime_config(db)
    user = await db.get(User, user_id, with_for_update=True)
    if not user:
        raise HTTPException(404, "用户不存在")
    await _ensure_user_can_book(db, user, now)

    total_slots = (config["close_hour"] - config["open_hour"]) * 60 // config["slot_minutes"]
    if data.end_slot > total_slots:
        raise HTTPException(400, "预约时间超出开放时段")
    if data.date < now.date() or data.date > now.date() + timedelta(days=config["advance_days"]):
        raise HTTPException(400, f"仅可预约今天起{config['advance_days']}天内的日期")
    if slot_datetime(data.date, data.start_slot, config) <= now:
        raise HTTPException(400, "不能预约已经开始的时段")
    requested_minutes = (data.end_slot - data.start_slot) * config["slot_minutes"]
    start_minute = config["open_hour"] * 60 + data.start_slot * config["slot_minutes"]
    end_minute = config["open_hour"] * 60 + data.end_slot * config["slot_minutes"]
    used_minutes = await _daily_minutes(db, user_id, data.date, config)
    if used_minutes + requested_minutes > config["max_minutes_per_day"]:
        raise HTTPException(400, f"单日累计预约不得超过{config['max_minutes_per_day'] // 60}小时")

    result = await db.execute(
        select(RoomSceneRule).join(Room).options(selectinload(RoomSceneRule.room)).where(
            RoomSceneRule.scene == data.scene,
            RoomSceneRule.is_enabled.is_(True),
            Room.is_active.is_(True),
            Room.can_reserve.is_(True),
            RoomSceneRule.capacity >= data.people_count,
        ).order_by(RoomSceneRule.priority)
    )
    rules = list(result.scalars().unique())
    if not rules:
        raise HTTPException(409, "该场景没有可容纳当前人数的房间")

    # Lock physical rooms (not only scene-rule rows) in one stable order. Study
    # and meeting therefore serialize even though they use different rule rows.
    room_ids = {rule.room_id for rule in rules}
    if data.scene in (SceneType.event, SceneType.music):
        room_ids.update((await db.scalars(select(Room.id).where(Room.room_code.in_(("A103", "B102"))))).all())
    await db.execute(select(Room.id).where(Room.id.in_(room_ids)).order_by(Room.id).with_for_update())

    if data.scene == SceneType.music and await _event_music_conflicts(db, data.scene, data, start_minute, end_minute):
        raise HTTPException(409, "A103大型活动与B102音乐练习互斥，该时段不可预约")

    selected_rule = None
    for rule in rules:
        if await _candidate_available(db, rule, data, start_minute, end_minute):
            selected_rule = rule
            break
    if not selected_rule:
        raise HTTPException(409, "候选房间在该时段均已占用或共享容量不足")

    # Large events have explicit priority over not-yet-started music bookings.
    if data.scene == SceneType.event:
        for conflict in await _event_music_conflicts(db, data.scene, data, start_minute, end_minute):
            conflict.status = ReservationStatus.rejected
            conflict.review_note = "因A103大型活动最高优先级规则自动释放B102"
            conflict.reviewed_at = now
            _queue_notification(db, conflict.user_id, conflict.id, NotificationType.review_result, {
                "result": "rejected", "reason": conflict.review_note,
            })

    reservation = Reservation(
        user_id=user_id,
        room_id=selected_rule.room_id,
        date=data.date,
        start_slot=data.start_slot,
        end_slot=data.end_slot,
        start_minute=start_minute,
        end_minute=end_minute,
        start_hour=config["open_hour"] + data.start_slot * config["slot_minutes"] // 60,
        end_hour=config["open_hour"] + data.end_slot * config["slot_minutes"] // 60,
        scene=data.scene,
        usage_mode=selected_rule.usage_mode,
        people_count=data.people_count,
        purpose=data.purpose.strip(),
        status=ReservationStatus.pending,
    )
    db.add(reservation)
    await db.flush()
    _queue_notification(db, user_id, reservation.id, NotificationType.submitted, {
        "room": f"{selected_rule.room.room_code} {selected_rule.room.name}",
        "date": data.date.isoformat(),
        "time": f"{slot_label(data.start_slot, config)}-{slot_label(data.end_slot, config)}",
    })
    await db.commit()
    return await get_reservation(db, reservation.id)


def _queue_notification(db: AsyncSession, user_id: int, reservation_id: int | None, kind: NotificationType, payload: dict, scheduled_at: datetime | None = None) -> None:
    db.add(Notification(user_id=user_id, reservation_id=reservation_id, type=kind, payload=payload, scheduled_at=scheduled_at or local_now()))


async def get_reservation(db: AsyncSession, reservation_id: int) -> Reservation | None:
    result = await db.execute(select(Reservation).options(
        joinedload(Reservation.room).selectinload(Room.scene_rules),
        joinedload(Reservation.user),
        joinedload(Reservation.cleanup),
    ).where(Reservation.id == reservation_id))
    return result.unique().scalar_one_or_none()


async def get_user_reservations(db: AsyncSession, user_id: int, status_filter: ReservationStatus | None = None) -> list[Reservation]:
    await refresh_reservation_states(db)
    query = select(Reservation).options(
        joinedload(Reservation.room).selectinload(Room.scene_rules),
        joinedload(Reservation.user),
        joinedload(Reservation.cleanup),
    ).where(Reservation.user_id == user_id)
    if status_filter:
        query = query.where(Reservation.status == status_filter)
    result = await db.execute(query.order_by(Reservation.date.desc(), Reservation.start_slot.desc()))
    return list(result.scalars().unique())


async def cancel_reservation(db: AsyncSession, reservation_id: int, user_id: int) -> Reservation | None:
    reservation = await db.get(Reservation, reservation_id, with_for_update=True)
    if not reservation or reservation.user_id != user_id or reservation.status not in (ReservationStatus.pending, ReservationStatus.approved, ReservationStatus.active):
        return None
    config = await get_runtime_config(db)
    deadline = reservation_start(reservation, config) - timedelta(minutes=config["cancel_deadline_minutes"])
    if local_now() >= deadline:
        raise ValueError(f"已超过开始前{config['cancel_deadline_minutes']}分钟的取消截止时间")
    reservation.status = ReservationStatus.cancelled
    reservation.cancelled_at = local_now()
    await db.commit()
    return reservation


async def checkin_reservation(db: AsyncSession, reservation_id: int, user_id: int) -> Reservation | None:
    reservation = await db.get(Reservation, reservation_id, with_for_update=True)
    if not reservation or reservation.user_id != user_id or reservation.status not in (ReservationStatus.approved, ReservationStatus.active):
        return None
    config = await get_runtime_config(db)
    now = local_now()
    start = reservation_start(reservation, config)
    if now < start - timedelta(minutes=15) or now > start + timedelta(minutes=config["checkin_grace_minutes"]):
        raise ValueError("仅可在开始前15分钟至签到宽限期内签到")
    reservation.status = ReservationStatus.in_use
    reservation.checked_in_at = now
    await db.commit()
    return reservation


async def submit_cleanup(db: AsyncSession, reservation_id: int, user_id: int, photo_urls: list[str]) -> Reservation:
    reservation = (await db.execute(select(Reservation).options(joinedload(Reservation.cleanup)).where(
        Reservation.id == reservation_id
    ).with_for_update())).scalar_one_or_none()
    if not reservation or reservation.user_id != user_id:
        raise HTTPException(404, "预约不存在")
    config = await get_runtime_config(db)
    if local_now() < reservation_end(reservation, config):
        raise HTTPException(400, "预约结束后才能提交清扫照片")
    if reservation.status not in (ReservationStatus.in_use, ReservationStatus.checked_in, ReservationStatus.cleanup_pending, ReservationStatus.cleanup_rejected):
        raise HTTPException(409, "当前预约状态不能提交清扫照片")
    cleanup = reservation.cleanup
    if cleanup:
        cleanup.photo_urls = photo_urls
        cleanup.status = CleanupStatus.pending
        cleanup.submitted_at = local_now()
        cleanup.review_note = None
    else:
        cleanup = CleanupVerification(reservation_id=reservation.id, photo_urls=photo_urls)
        db.add(cleanup)
    reservation.status = ReservationStatus.cleanup_pending
    await db.commit()
    return await get_reservation(db, reservation.id)


async def review_reservations(db: AsyncSession, request: ReservationReviewRequest, admin_id: int, auto: bool = False) -> dict:
    result = await db.execute(select(Reservation).where(
        Reservation.id.in_(request.reservation_ids),
        Reservation.status == ReservationStatus.pending,
    ).with_for_update())
    reservations = list(result.scalars())
    now = local_now()
    target = ReservationStatus.approved if request.decision.value == "approved" else ReservationStatus.rejected
    for reservation in reservations:
        reservation.status = target
        reservation.review_note = request.note or ("系统23:00自动审批" if auto else "")
        reservation.reviewed_by = None if auto else admin_id
        reservation.reviewed_at = now
        reservation.auto_approved = auto
        _queue_notification(db, reservation.user_id, reservation.id, NotificationType.review_result, {
            "result": target.value, "reason": reservation.review_note or "",
        })
        if target == ReservationStatus.approved and reservation.start_slot is not None:
            config = await get_runtime_config(db)
            remind_at = slot_datetime(reservation.date, reservation.start_slot, config) - timedelta(minutes=config["reminder_minutes"])
            _queue_notification(db, reservation.user_id, reservation.id, NotificationType.starting_soon, {
                "date": reservation.date.isoformat(),
            }, remind_at)
    await db.commit()
    return {"processed": len(reservations), "requested": len(request.reservation_ids), "status": target.value}


async def auto_approve_pending(db: AsyncSession) -> int:
    ids = list((await db.scalars(select(Reservation.id).where(Reservation.status == ReservationStatus.pending))).all())
    if not ids:
        return 0
    from app.models import ReviewDecision
    result = await review_reservations(db, ReservationReviewRequest(
        reservation_ids=ids, decision=ReviewDecision.approved, note="系统23:00自动审批"
    ), admin_id=0, auto=True)
    return result["processed"]


async def add_restriction(db: AsyncSession, user_id: int, data: RestrictionCreate, admin_id: int, commit: bool = True) -> BookingRestriction:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    now = local_now()
    ends_at = None if data.level == RestrictionLevel.permanent else now + timedelta(days=data.days or 1)
    restriction = BookingRestriction(user_id=user_id, level=data.level, reason=data.reason, ends_at=ends_at, created_by=admin_id)
    db.add(restriction)
    _queue_notification(db, user_id, None, NotificationType.restriction, {
        "level": data.level.value, "reason": data.reason, "ends_at": ends_at.isoformat() if ends_at else "永久",
    })
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
    await db.commit()
    return True


async def review_cleanup(db: AsyncSession, cleanup_id: int, request: CleanupReviewRequest, admin_id: int) -> CleanupVerification:
    cleanup = await db.get(CleanupVerification, cleanup_id, with_for_update=True)
    if not cleanup or cleanup.status != CleanupStatus.pending:
        raise HTTPException(404, "待复核记录不存在")
    reservation = await db.get(Reservation, cleanup.reservation_id)
    approved = request.decision.value == "approved"
    cleanup.status = CleanupStatus.approved if approved else CleanupStatus.rejected
    cleanup.reviewed_by = admin_id
    cleanup.reviewed_at = local_now()
    cleanup.review_note = request.note
    reservation.status = ReservationStatus.completed if approved else ReservationStatus.cleanup_rejected
    if not approved and request.restrict_user:
        await add_restriction(db, reservation.user_id, RestrictionCreate(
            level=request.restriction_level,
            reason=request.note or "现场清扫核验未通过",
            days=request.restriction_days,
        ), admin_id, commit=False)
    await db.commit()
    await db.refresh(cleanup)
    return cleanup


async def list_admin_reservations(db: AsyncSession, day: date | None = None, reservation_status: ReservationStatus | None = None) -> list[Reservation]:
    await refresh_reservation_states(db)
    query = select(Reservation).options(
        joinedload(Reservation.room).selectinload(Room.scene_rules),
        joinedload(Reservation.user),
        joinedload(Reservation.cleanup),
    )
    if day:
        query = query.where(Reservation.date == day)
    if reservation_status:
        query = query.where(Reservation.status == reservation_status)
    result = await db.execute(query.order_by(Reservation.created_at.desc()))
    return list(result.scalars().unique())


async def get_all_users(db: AsyncSession) -> list[User]:
    return list((await db.scalars(select(User).order_by(User.student_id))).all())


async def set_counselor(db: AsyncSession, student_ids: list[str]) -> int:
    users = list((await db.scalars(select(User).where(User.student_id.in_(student_ids)))).all())
    for user in users:
        user.role = UserRole.counselor
    await db.commit()
    return len(users)


async def create_counselor_user(db: AsyncSession, student_id: str, name: str, phone: str, class_name: str, password_hash: str) -> User:
    user = await get_user_by_student_id(db, student_id)
    if user:
        user.role = UserRole.counselor
        user.name, user.phone, user.class_name = name, phone, class_name
    else:
        user = User(student_id=student_id, name=name, phone=phone, class_name=class_name, password_hash=password_hash, role=UserRole.counselor)
        db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_counselors(db: AsyncSession) -> list[User]:
    return list((await db.scalars(select(User).where(User.role == UserRole.counselor).order_by(User.student_id))).all())
