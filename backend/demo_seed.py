"""Create deterministic, synthetic records for the local 15-minute demo only."""
from __future__ import annotations

import asyncio
import os
from datetime import timedelta

from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.database import async_session
from app.models import Reservation, ReservationStatus, Room, SceneType, UsageMode, User, UserRole, local_now
from seed import seed


DEMO_PASSWORD = "Demo1234"
DEMO_USERS = (
    ("20269901", "演示学生", "13900009901", "2599", UserRole.student),
    ("20269902", "演示辅导员", "13900009902", "2599", UserRole.counselor),
)


async def upsert_user(db, student_id: str, name: str, phone: str, class_name: str, role: UserRole) -> User:
    user = await db.scalar(select(User).where(User.student_id == student_id))
    values = {
        "name": name,
        "phone": phone,
        "class_name": class_name,
        "role": role,
        "is_active": True,
        "password_hash": hash_password(DEMO_PASSWORD),
    }
    if user:
        for key, value in values.items():
            setattr(user, key, value)
        return user
    user = User(student_id=student_id, **values)
    db.add(user)
    await db.flush()
    return user


async def upsert_reservation(db, *, user: User, room: Room, marker: str, **values) -> None:
    reservation = await db.scalar(select(Reservation).where(
        Reservation.user_id == user.id,
        Reservation.purpose == marker,
    ))
    if reservation:
        for key, value in values.items():
            setattr(reservation, key, value)
        return
    db.add(Reservation(user_id=user.id, room_id=room.id, purpose=marker, **values))


async def create_demo_data() -> None:
    if os.getenv("ALLOW_DEMO_SEED") != "1":
        raise RuntimeError("演示数据仅在显式设置 ALLOW_DEMO_SEED=1 时生成")
    if settings.is_production or not settings.DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("演示数据只允许写入本地 development SQLite，禁止用于生产/PostgreSQL")

    await seed()
    async with async_session() as db:
        users = {
            row[0]: await upsert_user(db, *row)
            for row in DEMO_USERS
        }
        rooms = {
            code: await db.scalar(select(Room).where(Room.room_code == code))
            for code in ("A101", "A102", "A105", "A106")
        }
        if any(room is None for room in rooms.values()):
            raise RuntimeError("基础房间未正确初始化")

        now = local_now()
        # Keep the synthetic approved reservation inside the check-in window at
        # any time of day; 23:59 avoids rolling a 24:00 value into tomorrow.
        rounded = min(1439, int(round((now.hour * 60 + now.minute) / 30) * 30))
        start_slot = max(0, (rounded - 8 * 60) // 30)
        common = {"people_count": 1, "campus_card_photo_url": None, "campus_card_media_id": None}

        await upsert_reservation(
            db, user=users["20269901"], room=rooms["A102"], marker="[演示] 待管理员审核的个人自习",
            date=now.date() + timedelta(days=1), start_slot=4, end_slot=6,
            start_minute=600, end_minute=660, start_hour=10, end_hour=11,
            scene=SceneType.study, usage_mode=UsageMode.shared, status=ReservationStatus.pending,
            **common,
        )
        await upsert_reservation(
            db, user=users["20269901"], room=rooms["A101"], marker="[演示] 当前签到窗口预约",
            date=now.date(), start_slot=start_slot, end_slot=start_slot + 1,
            start_minute=rounded, end_minute=rounded + 30,
            start_hour=rounded // 60, end_hour=(rounded + 30) // 60,
            scene=SceneType.meeting, usage_mode=UsageMode.exclusive, status=ReservationStatus.approved,
            **common,
        )
        await upsert_reservation(
            db, user=users["20269901"], room=rooms["A105"], marker="[演示] 待上传清扫照片",
            date=now.date() - timedelta(days=1), start_slot=4, end_slot=5,
            start_minute=600, end_minute=630, start_hour=10, end_hour=10,
            scene=SceneType.meeting, usage_mode=UsageMode.exclusive, status=ReservationStatus.cleanup_pending,
            **common,
        )
        await upsert_reservation(
            db, user=users["20269902"], room=rooms["A106"], marker="[演示] 辅导员 A106 预约",
            date=now.date() + timedelta(days=1), start_slot=8, end_slot=10,
            start_minute=720, end_minute=780, start_hour=12, end_hour=13,
            scene=SceneType.meeting, usage_mode=UsageMode.exclusive, status=ReservationStatus.pending,
            **common,
        )
        await db.commit()

    print("Synthetic demo ready: 20269901 / 20269902, password Demo1234; local use only.")


if __name__ == "__main__":
    asyncio.run(create_demo_data())
