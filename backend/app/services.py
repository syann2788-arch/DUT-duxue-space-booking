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
    MediaPurpose,
    PrivateMedia,
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
    Violation,
    ViolationType,
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
    integer_keys = set(DEFAULT_RUNTIME_CONFIG) - {"auto_approval_time"}
    invalid_integer = next((key for key in sorted(integer_keys) if isinstance(config.get(key), bool) or not isinstance(config.get(key), int)), None)
    if invalid_integer:
        raise HTTPException(400, f"配置项 {invalid_integer} 必须为整数")
    if config["open_hour"] < 0 or config["close_hour"] > 24 or config["open_hour"] >= config["close_hour"]:
        raise HTTPException(400, "开放时段配置无效")
    if config["slot_minutes"] not in (15, 30, 60):
        raise HTTPException(400, "预约粒度只能为15、30或60分钟")
    if 60 % config["slot_minutes"]:
        raise HTTPException(400, "预约粒度必须整除60分钟")
    if config["max_minutes_per_day"] < config["slot_minutes"]:
        raise HTTPException(400, "单日时长上限不能小于一个时段")
    if config["max_minutes_per_day"] % config["slot_minutes"]:
        raise HTTPException(400, "单日时长上限必须是预约粒度的整数倍")
    if config["advance_days"] < 0 or config["cancel_deadline_minutes"] < 0 or config["checkin_grace_minutes"] < 0 or config["reminder_minutes"] < 0:
        raise HTTPException(400, "预约天数及时间窗口不能为负数")
    if config["temporary_ban_days"] < 1 or config["violation_threshold"] < 1 or config["violation_ban_days"] < 1:
        raise HTTPException(400, "限制天数和违约阈值必须大于0")
    if not 0 <= config["music_a103_start_hour"] < config["music_a103_end_hour"] <= 24:
        raise HTTPException(400, "A103钢琴开放时段配置无效")
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
    result = await db.execute(
        select(Reservation)
        .where(
            Reservation.status.in_(OCCUPYING_STATUSES),
            Reservation.date >= now.date() - timedelta(days=1),
            Reservation.date <= now.date(),
        )
        .with_for_update(skip_locked=True)
    )
    changed = False
    for reservation in result.scalars():
        if reservation.start_slot is None or reservation.end_slot is None:
            continue
        start = reservation_start(reservation, config)
        end = reservation_end(reservation, config)
        if reservation.status == ReservationStatus.pending and now >= start:
            reservation.status = ReservationStatus.rejected
            reservation.review_note = "审批超时：预约开始前未完成审核"
            reservation.reviewed_at = now
            _queue_notification(db, reservation.user_id, reservation.id, NotificationType.review_result, {
                "result": "rejected", "reason": reservation.review_note,
            })
            changed = True
        elif reservation.status in (ReservationStatus.approved, ReservationStatus.active) and now > start + timedelta(minutes=config["checkin_grace_minutes"]):
            reservation.status = ReservationStatus.missed
            await _record_violation(db, reservation.user_id, reservation.id, ViolationType.no_show, now, config)
            changed = True
        elif reservation.status in (ReservationStatus.in_use, ReservationStatus.checked_in) and now >= end:
            reservation.status = ReservationStatus.cleanup_pending
            _queue_notification(db, reservation.user_id, reservation.id, NotificationType.restriction, {
                "change": "cleanup_required", "reason": "预约已结束，请及时上传现场清扫照片后解锁下一次预约",
            })
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


async def get_active_restriction(db: AsyncSession, user: User, now: datetime | None = None) -> BookingRestriction | None:
    """Public read helper for profile/status endpoints."""
    return await _active_restriction(db, user, now or local_now())


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
    if restrictions:
        await db.commit()
    return len(restrictions)


async def _ensure_user_can_book(db: AsyncSession, user: User, now: datetime) -> None:
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    restriction = await _active_restriction(db, user, now)
    if restriction:
        until = restriction.ends_at.strftime("%Y-%m-%d %H:%M") if restriction.ends_at else "永久"
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"预约资格受限（{until}）：{restriction.reason}")
    unresolved = await db.scalar(select(func.count(Reservation.id)).where(
        Reservation.user_id == user.id,
        or_(
            and_(Reservation.status == ReservationStatus.cleanup_pending, ~Reservation.cleanup.has()),
            Reservation.status == ReservationStatus.cleanup_rejected,
        ),
    ))
    if unresolved:
        raise HTTPException(status.HTTP_409_CONFLICT, "请先上传上一笔预约的现场清扫照片")


async def _record_violation(
    db: AsyncSession,
    user_id: int,
    reservation_id: int,
    violation_type: ViolationType,
    now: datetime,
    config: dict | None = None,
) -> bool:
    """Record one auditable violation and apply each 3-strike ban exactly once."""
    # Serialize threshold counting per user so request-triggered refresh and the
    # worker cannot both create the same N-strike restriction.
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
    config = config or await get_runtime_config(db)
    threshold = int(config["violation_threshold"])
    if count % threshold == 0:
        days = int(config["violation_ban_days"])
        await add_restriction(
            db,
            user_id,
            RestrictionCreate(level=RestrictionLevel.timed, days=days, reason=f"累计{count}次违约，自动禁约{days}天"),
            admin_id=None,
            commit=False,
        )
    return True


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
    # A NULL mode denotes an imported V1 reservation. V1 bookings occupied the
    # whole room, so treat unknown legacy rows conservatively as exclusive.
    if any(item.usage_mode != UsageMode.shared for item in existing):
        return False
    # Capacity is a peak-at-one-time constraint. Summing every reservation that
    # touches a multi-slot request overcounts disjoint bookings in that range.
    boundaries = {start_minute, end_minute}
    for item in existing:
        boundaries.add(max(start_minute, int(item.start_minute)))
        boundaries.add(min(end_minute, int(item.end_minute)))
    ordered = sorted(boundaries)
    for segment_start, segment_end in zip(ordered, ordered[1:]):
        if segment_start >= segment_end:
            continue
        occupied = sum(
            item.people_count
            for item in existing
            if int(item.start_minute) < segment_end and int(item.end_minute) > segment_start
        )
        if occupied + data.people_count > rule.capacity:
            return False
    return True


def _room_permission_clause(role: UserRole):
    """Translate an authenticated user's role into reservable room scope."""
    if role in (UserRole.counselor, UserRole.admin):
        return Room.who_can_reserve.in_(("all", "counselor"))
    return Room.who_can_reserve == "all"


async def get_scene_availability(
    db: AsyncSession,
    scene: SceneType,
    day: date,
    people_count: int,
    role: UserRole,
) -> dict:
    """Return single-slot availability across all candidate rooms for a scene.

    This powers the native mini-program's visual slot grid.  It is deliberately
    advisory: the create transaction repeats every conflict and capacity check
    across the complete requested range before assigning a room.
    """
    config = await get_runtime_config(db)
    now = local_now()
    if day < now.date() or day > now.date() + timedelta(days=int(config["advance_days"])):
        raise HTTPException(400, f"仅可查询今天起{config['advance_days']}天内的日期")

    result = await db.execute(
        select(RoomSceneRule)
        .join(Room)
        .options(selectinload(RoomSceneRule.room))
        .where(
            RoomSceneRule.scene == scene,
            RoomSceneRule.is_enabled.is_(True),
            RoomSceneRule.capacity >= people_count,
            Room.is_active.is_(True),
            Room.can_reserve.is_(True),
            _room_permission_clause(role),
        )
        .order_by(RoomSceneRule.priority)
    )
    rules = list(result.scalars().unique())
    room_ids = {rule.room_id for rule in rules}
    reservations: list[Reservation] = []
    if room_ids:
        reservations = list((await db.execute(select(Reservation).where(
            Reservation.room_id.in_(room_ids),
            Reservation.date == day,
            Reservation.status.in_(OCCUPYING_STATUSES),
        ))).scalars())

    total_slots = (config["close_hour"] - config["open_hour"]) * 60 // config["slot_minutes"]
    slots = []
    for index in range(total_slots):
        start_minute = config["open_hour"] * 60 + index * config["slot_minutes"]
        end_minute = start_minute + config["slot_minutes"]
        available_room_ids: list[int] = []
        for rule in rules:
            if scene == SceneType.music and rule.room.room_code == "A103":
                piano_start = int(config["music_a103_start_hour"]) * 60
                piano_end = int(config["music_a103_end_hour"]) * 60
                if start_minute < piano_start or end_minute > piano_end:
                    continue
            existing = [
                item for item in reservations
                if item.room_id == rule.room_id
                and item.start_minute is not None
                and item.start_minute < end_minute
                and item.end_minute > start_minute
            ]
            if rule.usage_mode == UsageMode.exclusive:
                available = not existing
            else:
                available = (
                    not any(item.usage_mode != UsageMode.shared for item in existing)
                    and sum(item.people_count for item in existing) + people_count <= rule.capacity
                )
            if available:
                available_room_ids.append(rule.room_id)
        if day == now.date() and slot_datetime(day, index, config) <= now:
            available_room_ids = []
        slots.append({
            "slot": index,
            "label": f"{slot_label(index, config)}-{slot_label(index + 1, config)}",
            "available": bool(available_room_ids),
            # The client intersects these ids across a selected range. This
            # prevents adjacent slots in different rooms from looking like one
            # bookable continuous interval.
            "available_room_ids": available_room_ids,
        })
    return {"date": day.isoformat(), "scene": scene.value, "people_count": people_count, "slots": slots}


async def create_reservation(db: AsyncSession, user_id: int, data: ReservationCreate) -> Reservation:
    now = local_now()
    await refresh_reservation_states(db, now)
    config = await get_runtime_config(db)
    user = await db.get(User, user_id, with_for_update=True)
    if not user:
        raise HTTPException(404, "用户不存在")
    await _ensure_user_can_book(db, user, now)
    campus_card = await _claim_private_media(
        db, [data.campus_card_media_id], user_id, MediaPurpose.campus_card
    )

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
    user_overlap = await db.scalar(select(func.count(Reservation.id)).where(
        Reservation.user_id == user_id,
        Reservation.date == data.date,
        Reservation.status.in_(OCCUPYING_STATUSES),
        Reservation.start_minute < end_minute,
        Reservation.end_minute > start_minute,
    ))
    if user_overlap:
        raise HTTPException(409, "同一用户不能预约重叠时段")
    used_minutes = await _daily_minutes(db, user_id, data.date, config)
    if used_minutes + requested_minutes > config["max_minutes_per_day"]:
        raise HTTPException(400, f"单日累计预约不得超过{config['max_minutes_per_day'] // 60}小时")

    rule_filters = [
        RoomSceneRule.scene == data.scene,
        RoomSceneRule.is_enabled.is_(True),
        Room.is_active.is_(True),
        Room.can_reserve.is_(True),
        _room_permission_clause(user.role),
    ]
    rule_filters.append(RoomSceneRule.capacity >= data.people_count)
    result = await db.execute(
        select(RoomSceneRule).join(Room).options(selectinload(RoomSceneRule.room)).where(*rule_filters).order_by(RoomSceneRule.priority)
    )
    rules = list(result.scalars().unique())
    if not rules:
        raise HTTPException(409, "该场景没有可容纳当前人数的房间")

    # Lock physical rooms (not only scene-rule rows) in one stable order. Study
    # and meeting therefore serialize even though they use different rule rows.
    room_ids = {rule.room_id for rule in rules}
    await db.execute(select(Room.id).where(Room.id.in_(room_ids)).order_by(Room.id).with_for_update())

    selected_rule = None
    for rule in rules:
        if data.scene == SceneType.music and rule.room.room_code == "A103":
            piano_start = int(config["music_a103_start_hour"]) * 60
            piano_end = int(config["music_a103_end_hour"]) * 60
            if start_minute < piano_start or end_minute > piano_end:
                continue
        if await _candidate_available(db, rule, data, start_minute, end_minute):
            selected_rule = rule
            break
    if not selected_rule:
        raise HTTPException(409, "候选房间在该时段均已占用或共享容量不足")

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
        campus_card_photo_url=None,
        campus_card_media_id=campus_card[0].id,
        status=ReservationStatus.pending,
    )
    db.add(reservation)
    await db.flush()
    campus_card[0].reservation_id = reservation.id
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


async def _claim_private_media(
    db: AsyncSession,
    media_ids: list[str],
    owner_id: int,
    purpose: MediaPurpose,
    reservation_id: int | None = None,
) -> list[PrivateMedia]:
    result = await db.execute(
        select(PrivateMedia)
        .where(PrivateMedia.id.in_(media_ids))
        .order_by(PrivateMedia.id)
        .with_for_update()
    )
    media = list(result.scalars())
    found = {item.id for item in media}
    if len(found) != len(set(media_ids)):
        raise HTTPException(400, "照片凭证不存在")
    now = local_now()
    for item in media:
        if item.owner_id != owner_id or item.purpose != purpose or not item.is_active:
            raise HTTPException(403, "照片凭证不属于当前用户或用途不匹配")
        if item.expires_at <= now:
            raise HTTPException(410, "照片凭证已超过保留期限")
        if item.reservation_id is not None and item.reservation_id != reservation_id:
            raise HTTPException(409, "照片凭证已用于其他预约")
    return media


async def purge_expired_private_media(db: AsyncSession) -> int:
    """Delete expired sensitive files and retain an inactive audit record."""
    from pathlib import Path

    from app.config import settings

    expired = list((await db.scalars(
        select(PrivateMedia)
        .where(PrivateMedia.deleted_at.is_(None), PrivateMedia.expires_at <= local_now())
        .with_for_update()
    )).all())
    private_root = Path(settings.PRIVATE_UPLOAD_DIR)
    deleted_at = local_now()
    for item in expired:
        if Path(item.storage_key).name == item.storage_key:
            (private_root / item.storage_key).unlink(missing_ok=True)
        item.is_active = False
        item.deleted_at = deleted_at
    if expired:
        await db.commit()
    return len(expired)


async def submit_cleanup(db: AsyncSession, reservation_id: int, user_id: int, media_ids: list[str]) -> Reservation:
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
    media = await _claim_private_media(
        db, media_ids, user_id, MediaPurpose.cleanup, reservation.id
    )
    cleanup = reservation.cleanup
    if cleanup:
        previous_ids = set(cleanup.media_ids or [])
        cleanup.photo_urls = []
        cleanup.media_ids = media_ids
        cleanup.status = CleanupStatus.pending
        cleanup.submitted_at = local_now()
        cleanup.review_note = None
    else:
        previous_ids = set()
        cleanup = CleanupVerification(reservation_id=reservation.id, photo_urls=[], media_ids=media_ids)
        db.add(cleanup)
    for item in media:
        item.reservation_id = reservation.id
    retired_ids = previous_ids - set(media_ids)
    if retired_ids:
        retired = list((await db.scalars(select(PrivateMedia).where(
            PrivateMedia.id.in_(retired_ids), PrivateMedia.owner_id == user_id
        ))).all())
        for item in retired:
            item.is_active = False
    reservation.status = ReservationStatus.cleanup_pending
    await db.commit()
    return await get_reservation(db, reservation.id)


async def review_reservations(db: AsyncSession, request: ReservationReviewRequest, admin_id: int, auto: bool = False) -> dict:
    await refresh_reservation_states(db)
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


async def add_restriction(db: AsyncSession, user_id: int, data: RestrictionCreate, admin_id: int | None, commit: bool = True) -> BookingRestriction:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    now = local_now()
    ends_at = None if data.level == RestrictionLevel.permanent else now + timedelta(days=data.days or 1)
    restriction = BookingRestriction(user_id=user_id, level=data.level, reason=data.reason, ends_at=ends_at, created_by=admin_id)
    db.add(restriction)
    await db.flush()
    _queue_notification(db, user_id, None, NotificationType.restriction, {
        "change": "restricted", "restriction_id": restriction.id, "level": data.level.value,
        "reason": data.reason, "ends_at": ends_at.isoformat() if ends_at else "永久",
    })
    if ends_at:
        _queue_notification(db, user_id, None, NotificationType.restriction, {
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
    pending_expiry = list((await db.scalars(select(Notification).where(
        Notification.user_id == restriction.user_id,
        Notification.type == NotificationType.restriction,
        Notification.status == NotificationStatus.pending,
    ))).all())
    for notification in pending_expiry:
        if notification.payload.get("change") == "expired" and notification.payload.get("restriction_id") == restriction.id:
            await db.delete(notification)
    _queue_notification(db, restriction.user_id, None, NotificationType.restriction, {
        "change": "revoked", "level": "revoked", "reason": "管理员已解除预约限制", "ends_at": local_now().isoformat(),
    })
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
    if not approved:
        _queue_notification(db, reservation.user_id, reservation.id, NotificationType.restriction, {
            "change": "cleanup_rejected", "reason": request.note or "清扫照片核验不合格，请重新上传",
        })
        await _record_violation(
            db,
            reservation.user_id,
            reservation.id,
            ViolationType.cleanup_failed,
            local_now(),
        )
    if not approved and request.restrict_user:
        await add_restriction(db, reservation.user_id, RestrictionCreate(
            level=request.restriction_level,
            reason=request.note or "现场清扫核验未通过",
            days=request.restriction_days,
        ), admin_id, commit=False)
    await db.commit()
    await db.refresh(cleanup)
    return cleanup


async def list_admin_reservations(
    db: AsyncSession,
    day: date | None = None,
    reservation_status: ReservationStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    scene: SceneType | None = None,
) -> list[Reservation]:
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
    result = await db.execute(query.order_by(Reservation.created_at.desc()))
    return list(result.scalars().unique())


async def get_all_users(db: AsyncSession, search: str | None = None) -> list[User]:
    query = select(User)
    if search and search.strip():
        keyword = f"%{search.strip()}%"
        query = query.where(or_(
            User.student_id.ilike(keyword),
            User.name.ilike(keyword),
            User.phone.ilike(keyword),
            User.class_name.ilike(keyword),
        ))
    return list((await db.scalars(query.order_by(User.student_id))).all())


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
