"""Production-database concurrency gate; enabled explicitly in CI."""
import asyncio
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="requires an isolated PostgreSQL database",
)


async def booking_scenario():
    from app.auth import hash_password
    from app.database import async_session
    from app.models import MediaPurpose, PrivateMedia, Reservation, User, local_now
    from app.schemas import ReservationCreate
    from app.domain.reservations import create_reservation
    from seed import seed

    await seed()
    async with async_session() as db:
        await db.execute(delete(Reservation))
        await db.commit()
        users = []
        media_ids = []
        for index in range(2):
            user = User(
                student_id=f"{int(uuid4().hex[:10], 16):010d}{index}"[-20:], name=f"并发用户{index}",
                phone=f"1399999999{index}", class_name="9901",
                password_hash=hash_password("Test1234"),
            )
            db.add(user)
            await db.flush()
            media_id = str(uuid4())
            db.add(PrivateMedia(
                id=media_id, owner_id=user.id, purpose=MediaPurpose.campus_card,
                storage_key=f"{media_id}.jpg", content_type="image/jpeg", size_bytes=10,
                expires_at=local_now() + timedelta(days=1),
            ))
            users.append(user.id)
            media_ids.append(media_id)
        await db.commit()

    day = local_now().date() + timedelta(days=1)

    async def reserve(user_id: int, media_id: str):
        async with async_session() as db:
            try:
                reservation = await create_reservation(db, user_id, ReservationCreate(
                    scene="event", date=day, start_slot=4, end_slot=6,
                    people_count=100, purpose="并发测试大型主题活动申请",
                    campus_card_media_id=media_id,
                ))
                return reservation.id
            except HTTPException as exc:
                await db.rollback()
                return exc.status_code

    outcomes = await asyncio.gather(
        reserve(users[0], media_ids[0]), reserve(users[1], media_ids[1])
    )
    async with async_session() as db:
        count = int(await db.scalar(select(func.count(Reservation.id)).where(
            Reservation.date == day,
            Reservation.start_slot == 4,
            Reservation.end_slot == 6,
        )) or 0)
    return outcomes, count


def test_postgresql_room_lock_prevents_double_booking():
    outcomes, count = asyncio.run(booking_scenario())
    assert count == 1
    assert sum(isinstance(item, int) and item == 409 for item in outcomes) == 1


async def leader_scenario():
    from app.tasks import leader_lock

    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold_lock():
        async with leader_lock() as acquired:
            assert acquired is True
            entered.set()
            await release.wait()

    first = asyncio.create_task(hold_lock())
    await entered.wait()
    async with leader_lock() as second_acquired:
        second = second_acquired
    release.set()
    await first
    return second


def test_postgresql_advisory_lock_allows_only_one_worker_leader():
    assert asyncio.run(leader_scenario()) is False
