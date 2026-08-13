"""Reservation allocation, lifecycle state, cancellation, and check-in."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.domain.common import (
    DAILY_LIMIT_STATUSES, OCCUPYING_STATUSES, queue_notification,
    reservation_end, reservation_start, slot_datetime, slot_label,
)
from app.domain.media import claim_private_media
from app.domain.restrictions import active_restriction, record_violation
from app.domain.settings import get_runtime_config
from app.models import (
    MediaPurpose, NotificationType, Reservation, ReservationStatus, Room,
    RoomSceneRule, SceneType, UsageMode, User, UserRole, ViolationType, local_now,
)
from app.schemas import ReservationCreate


async def refresh_reservation_states(db: AsyncSession, now: datetime | None = None) -> None:
    now = now or local_now()
    config = await get_runtime_config(db)
    result = await db.execute(select(Reservation).where(
        Reservation.status.in_(OCCUPYING_STATUSES),
        Reservation.date >= now.date() - timedelta(days=1),
        Reservation.date <= now.date(),
    ).with_for_update(skip_locked=True))
    changed = False
    for reservation in result.scalars():
        if reservation.start_slot is None or reservation.end_slot is None:
            continue
        start, end = reservation_start(reservation, config), reservation_end(reservation, config)
        if reservation.status == ReservationStatus.pending and now >= start:
            reservation.status = ReservationStatus.rejected
            reservation.review_note = "审批超时：预约开始前未完成审核"
            reservation.reviewed_at = now
            queue_notification(db, reservation.user_id, reservation.id, NotificationType.review_result, {
                "result": "rejected", "reason": reservation.review_note,
            })
            changed = True
        elif reservation.status in (ReservationStatus.approved, ReservationStatus.active) and now > start + timedelta(minutes=config["checkin_grace_minutes"]):
            reservation.status = ReservationStatus.missed
            await record_violation(db, reservation.user_id, reservation.id, ViolationType.no_show, now, config)
            changed = True
        elif reservation.status in (ReservationStatus.in_use, ReservationStatus.checked_in) and now >= end:
            reservation.status = ReservationStatus.cleanup_pending
            queue_notification(db, reservation.user_id, reservation.id, NotificationType.restriction, {
                "change": "cleanup_required", "reason": "预约已结束，请及时上传现场清扫照片后解锁下一次预约",
            })
            changed = True
    if changed:
        await db.commit()


async def ensure_user_can_book(db: AsyncSession, user: User, now: datetime) -> None:
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    restriction = await active_restriction(db, user, now)
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


async def _daily_minutes(db: AsyncSession, user_id: int, day: date, config: dict) -> int:
    result = await db.execute(select(
        Reservation.start_minute, Reservation.end_minute,
        Reservation.start_slot, Reservation.end_slot,
    ).where(
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


async def _candidate_available(db: AsyncSession, rule: RoomSceneRule, data: ReservationCreate, start_minute: int, end_minute: int) -> bool:
    existing = list((await db.execute(select(Reservation).where(
        Reservation.room_id == rule.room_id,
        Reservation.date == data.date,
        Reservation.status.in_(OCCUPYING_STATUSES),
        Reservation.start_minute < end_minute,
        Reservation.end_minute > start_minute,
    ).with_for_update())).scalars())
    if rule.usage_mode == UsageMode.exclusive:
        return not existing
    if any(item.usage_mode != UsageMode.shared for item in existing):
        return False
    boundaries = {start_minute, end_minute}
    for item in existing:
        boundaries.add(max(start_minute, int(item.start_minute)))
        boundaries.add(min(end_minute, int(item.end_minute)))
    ordered = sorted(boundaries)
    for segment_start, segment_end in zip(ordered, ordered[1:]):
        occupied = sum(item.people_count for item in existing if int(item.start_minute) < segment_end and int(item.end_minute) > segment_start)
        if occupied + data.people_count > rule.capacity:
            return False
    return True


def room_permission_clause(role: UserRole):
    if role in (UserRole.counselor, UserRole.admin):
        return Room.who_can_reserve.in_(("all", "counselor"))
    return Room.who_can_reserve == "all"


async def _candidate_rules(db: AsyncSession, scene: SceneType, people_count: int, role: UserRole) -> list[RoomSceneRule]:
    result = await db.execute(select(RoomSceneRule).join(Room).options(
        selectinload(RoomSceneRule.room)
    ).where(
        RoomSceneRule.scene == scene,
        RoomSceneRule.is_enabled.is_(True),
        RoomSceneRule.capacity >= people_count,
        Room.is_active.is_(True),
        Room.can_reserve.is_(True),
        room_permission_clause(role),
    ).order_by(RoomSceneRule.priority))
    return list(result.scalars().unique())


async def get_scene_availability(db: AsyncSession, scene: SceneType, day: date, people_count: int, role: UserRole) -> dict:
    config, now = await get_runtime_config(db), local_now()
    if day < now.date() or day > now.date() + timedelta(days=int(config["advance_days"])):
        raise HTTPException(400, f"仅可查询今天起{config['advance_days']}天内的日期")
    rules = await _candidate_rules(db, scene, people_count, role)
    room_ids = {rule.room_id for rule in rules}
    reservations = [] if not room_ids else list((await db.execute(select(Reservation).where(
        Reservation.room_id.in_(room_ids), Reservation.date == day,
        Reservation.status.in_(OCCUPYING_STATUSES),
    ))).scalars())
    total_slots = (config["close_hour"] - config["open_hour"]) * 60 // config["slot_minutes"]
    slots = []
    for index in range(total_slots):
        start_minute = config["open_hour"] * 60 + index * config["slot_minutes"]
        end_minute = start_minute + config["slot_minutes"]
        available_room_ids = []
        for rule in rules:
            if scene == SceneType.music and rule.room.room_code == "A103" and (
                start_minute < int(config["music_a103_start_hour"]) * 60
                or end_minute > int(config["music_a103_end_hour"]) * 60
            ):
                continue
            existing = [item for item in reservations if item.room_id == rule.room_id and item.start_minute is not None and item.start_minute < end_minute and item.end_minute > start_minute]
            available = not existing if rule.usage_mode == UsageMode.exclusive else (
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
    await ensure_user_can_book(db, user, now)
    campus_card = await claim_private_media(db, [data.campus_card_media_id], user_id, MediaPurpose.campus_card)
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
    if await db.scalar(select(func.count(Reservation.id)).where(
        Reservation.user_id == user_id, Reservation.date == data.date,
        Reservation.status.in_(OCCUPYING_STATUSES),
        Reservation.start_minute < end_minute, Reservation.end_minute > start_minute,
    )):
        raise HTTPException(409, "同一用户不能预约重叠时段")
    used_minutes = await _daily_minutes(db, user_id, data.date, config)
    if used_minutes + requested_minutes > config["max_minutes_per_day"]:
        raise HTTPException(400, f"单日累计预约不得超过{config['max_minutes_per_day'] // 60}小时")
    rules = await _candidate_rules(db, data.scene, data.people_count, user.role)
    if not rules:
        raise HTTPException(409, "该场景没有可容纳当前人数的房间")
    room_ids = {rule.room_id for rule in rules}
    await db.execute(select(Room.id).where(Room.id.in_(room_ids)).order_by(Room.id).with_for_update())
    selected_rule = None
    for rule in rules:
        if data.scene == SceneType.music and rule.room.room_code == "A103" and (
            start_minute < int(config["music_a103_start_hour"]) * 60
            or end_minute > int(config["music_a103_end_hour"]) * 60
        ):
            continue
        if await _candidate_available(db, rule, data, start_minute, end_minute):
            selected_rule = rule
            break
    if not selected_rule:
        raise HTTPException(409, "候选房间在该时段均已占用或共享容量不足")
    reservation = Reservation(
        user_id=user_id, room_id=selected_rule.room_id, date=data.date,
        start_slot=data.start_slot, end_slot=data.end_slot,
        start_minute=start_minute, end_minute=end_minute,
        start_hour=config["open_hour"] + data.start_slot * config["slot_minutes"] // 60,
        end_hour=config["open_hour"] + data.end_slot * config["slot_minutes"] // 60,
        scene=data.scene, usage_mode=selected_rule.usage_mode,
        people_count=data.people_count, purpose=data.purpose.strip(),
        campus_card_photo_url=None, campus_card_media_id=campus_card[0].id,
        status=ReservationStatus.pending,
    )
    db.add(reservation)
    await db.flush()
    campus_card[0].reservation_id = reservation.id
    queue_notification(db, user_id, reservation.id, NotificationType.submitted, {
        "room": f"{selected_rule.room.room_code} {selected_rule.room.name}",
        "date": data.date.isoformat(),
        "time": f"{slot_label(data.start_slot, config)}-{slot_label(data.end_slot, config)}",
    })
    await db.commit()
    return await get_reservation(db, reservation.id)


async def get_reservation(db: AsyncSession, reservation_id: int) -> Reservation | None:
    result = await db.execute(select(Reservation).options(
        joinedload(Reservation.room).selectinload(Room.scene_rules),
        joinedload(Reservation.user), joinedload(Reservation.cleanup),
    ).where(Reservation.id == reservation_id))
    return result.unique().scalar_one_or_none()


async def cancel_reservation(db: AsyncSession, reservation_id: int, user_id: int, now: datetime | None = None) -> Reservation | None:
    reservation = await db.get(Reservation, reservation_id, with_for_update=True)
    if not reservation or reservation.user_id != user_id or reservation.status not in (ReservationStatus.pending, ReservationStatus.approved, ReservationStatus.active):
        return None
    config, now = await get_runtime_config(db), now or local_now()
    deadline = reservation_start(reservation, config) - timedelta(minutes=config["cancel_deadline_minutes"])
    if now >= deadline:
        raise ValueError(f"已超过开始前{config['cancel_deadline_minutes']}分钟的取消截止时间")
    reservation.status, reservation.cancelled_at = ReservationStatus.cancelled, now
    await db.commit()
    return reservation


async def checkin_reservation(db: AsyncSession, reservation_id: int, user_id: int, now: datetime | None = None) -> Reservation | None:
    reservation = await db.get(Reservation, reservation_id, with_for_update=True)
    if not reservation or reservation.user_id != user_id or reservation.status not in (ReservationStatus.approved, ReservationStatus.active):
        return None
    config, now = await get_runtime_config(db), now or local_now()
    start = reservation_start(reservation, config)
    if now < start - timedelta(minutes=15) or now > start + timedelta(minutes=config["checkin_grace_minutes"]):
        raise ValueError("仅可在开始前15分钟至签到宽限期内签到")
    reservation.status, reservation.checked_in_at = ReservationStatus.in_use, now
    await db.commit()
    return reservation
